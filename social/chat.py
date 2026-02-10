from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from datetime import datetime, timezone

from core.database import get_db
from core.models import User, Conversation, Message, FriendRequest
from core.auth import get_current_user
from social.schemas import (
    SendMessageRequest,
    MessageOut,
    MessagesResponse,
    ConversationOut,
    ConversationsResponse,
    UserMiniOut,
    ChatSettingsResponse,
    ChatSettingsData,
    UpdateChatSettingsRequest,
)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


def _mini(u: User) -> UserMiniOut:
    return UserMiniOut(
        id=str(u.id),
        username=u.username,
        displayName=u.display_name,
        avatarUrl=u.avatar_url,
        rating=u.current_rating or 1200,
    )


def _pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def _are_friends(db: Session, a: str, b: str) -> bool:
    fr = db.query(FriendRequest).filter(
        FriendRequest.status == "ACCEPTED",
        or_(
            and_(FriendRequest.requester_id == a, FriendRequest.addressee_id == b),
            and_(FriendRequest.requester_id == b, FriendRequest.addressee_id == a),
        ),
    ).first()
    return fr is not None


def _visible_for_user_filter(user_id: str):

    return or_(
        and_(Message.sender_id == user_id, Message.deleted_by_sender.is_(False)),
        and_(Message.recipient_id == user_id, Message.deleted_by_recipient.is_(False)),
    )


def _get_or_create_conversation(db: Session, user_a: str, user_b: str) -> Conversation:
    u1, u2 = _pair(str(user_a), str(user_b))
    convo = db.query(Conversation).filter(
        Conversation.user1_id == u1,
        Conversation.user2_id == u2,
    ).first()
    if convo:
        return convo

    convo = Conversation(
        user1_id=u1,
        user2_id=u2,
        created_at=datetime.now(timezone.utc),
    )
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo


@router.get("/settings", response_model=ChatSettingsResponse)
def get_chat_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {
        "success": True,
        "data": ChatSettingsData(allowNonFriendMessages=bool(getattr(current_user, "allow_non_friend_messages", True))),
    }


@router.put("/settings", response_model=ChatSettingsResponse)
def update_chat_settings(
    payload: UpdateChatSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = db.query(User).filter(User.id == current_user.id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.allow_non_friend_messages = bool(payload.allowNonFriendMessages)
    db.commit()

    return {
        "success": True,
        "data": ChatSettingsData(allowNonFriendMessages=bool(user.allow_non_friend_messages)),
    }


@router.post("/send")
def send_message(
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if str(payload.toUserId) == str(current_user.id):
        raise HTTPException(status_code=400, detail="Cannot message yourself")

    recipient = db.query(User).filter(User.id == payload.toUserId).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

   
    allow_non_friends = bool(getattr(recipient, "allow_non_friend_messages", True))
    if not allow_non_friends and not _are_friends(db, str(current_user.id), str(recipient.id)):
        raise HTTPException(status_code=403, detail="This user only allows messages from friends")

    convo = _get_or_create_conversation(db, str(current_user.id), str(recipient.id))

    msg = Message(
        conversation_id=str(convo.id),
        sender_id=str(current_user.id),
        recipient_id=str(recipient.id),
        content=payload.content.strip(),
        created_at=datetime.now(timezone.utc),
        deleted_by_sender=False,
        deleted_by_recipient=False,
    )
    db.add(msg)

    convo.last_message_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)

    return {
        "success": True,
        "data": {
            "id": str(msg.id),
            "conversationId": str(convo.id),
            "senderId": str(msg.sender_id),
            "recipientId": str(msg.recipient_id),
            "content": msg.content,
            "createdAt": msg.created_at,
            "readAt": msg.read_at,
        },
    }


@router.delete("/messages/{message_id}")
def delete_message(
    message_id: str,
    forEveryone: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msg = db.query(Message).filter(Message.id == message_id).with_for_update().first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    uid = str(current_user.id)

    # Sender can delete for self OR everyone
    if str(msg.sender_id) == uid:
        if forEveryone:
            msg.deleted_by_sender = True
            msg.deleted_by_recipient = True
            db.commit()
            return {"success": True, "message": "Deleted for everyone"}
        else:
            msg.deleted_by_sender = True
            db.commit()
            return {"success": True, "message": "Deleted for you"}

    # Recipient can only delete for self
    if str(msg.recipient_id) == uid:
        msg.deleted_by_recipient = True
        db.commit()
        return {"success": True, "message": "Deleted for you"}

    raise HTTPException(status_code=403, detail="Not allowed")


@router.get("/conversations", response_model=ConversationsResponse)
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(30, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    uid = str(current_user.id)

    convos = (
        db.query(Conversation)
        .filter(or_(Conversation.user1_id == uid, Conversation.user2_id == uid))
        .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    out = []
    for c in convos:
        other_id = c.user2_id if str(c.user1_id) == uid else c.user1_id
        other = db.query(User).filter(User.id == other_id).first()

        # ✅ last visible message for this user
        last_msg = (
            db.query(Message)
            .filter(Message.conversation_id == c.id)
            .filter(_visible_for_user_filter(uid))
            .order_by(Message.created_at.desc())
            .first()
        )

        unread = (
            db.query(Message)
            .filter(
                Message.conversation_id == c.id,
                Message.recipient_id == uid,
                Message.read_at.is_(None),
                Message.deleted_by_recipient.is_(False),
            )
            .count()
        )

        out.append(
            ConversationOut(
                id=str(c.id),
                otherUser=_mini(other) if other else UserMiniOut(id=str(other_id), username="Unknown", displayName="Unknown"),
                lastMessage=(last_msg.content[:120] if last_msg else None),
                lastMessageAt=(last_msg.created_at if last_msg else c.last_message_at),
                unreadCount=int(unread),
            )
        )

    return {"success": True, "data": out}


@router.get("/conversations/{conversation_id}/messages", response_model=MessagesResponse)
def get_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    uid = str(current_user.id)

    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if uid not in (str(convo.user1_id), str(convo.user2_id)):
        raise HTTPException(status_code=403, detail="Not allowed")

    base = (
        db.query(Message)
        .filter(Message.conversation_id == convo.id)
        .filter(_visible_for_user_filter(uid))
    )

    total = base.count()
    msgs = (
        base.order_by(Message.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    data = [
        MessageOut(
            id=str(m.id),
            conversationId=str(m.conversation_id),
            senderId=str(m.sender_id),
            recipientId=str(m.recipient_id),
            content=m.content,
            createdAt=m.created_at,
            readAt=m.read_at,
        )
        for m in msgs
    ]

    return {"success": True, "data": data, "pagination": {"total": total, "limit": limit, "offset": offset}}


@router.post("/messages/{message_id}/read")
def mark_read(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msg = db.query(Message).filter(Message.id == message_id).with_for_update().first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    if str(msg.recipient_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not allowed")

    if msg.deleted_by_recipient:
        return {"success": True, "message": "Message deleted for you"}

    if msg.read_at:
        return {"success": True, "message": "Already read"}

    msg.read_at = datetime.now(timezone.utc)
    db.commit()

    return {"success": True, "message": "Marked as read"}
