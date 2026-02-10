from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime, timezone

from core.database import get_db
from core.models import User, FriendRequest
from core.auth import get_current_user
from social.schemas import UserMiniOut, FriendRequestOut, FriendsListResponse

router = APIRouter(prefix="/api/friends", tags=["Friends"])


def _mini(u: User) -> UserMiniOut:
    return UserMiniOut(
        id=str(u.id),
        username=u.username,
        displayName=u.display_name,
        avatarUrl=u.avatar_url,
        rating=u.current_rating or 1200,
    )


@router.post("/request/{target_user_id}")
def send_friend_request(
    target_user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if str(current_user.id) == str(target_user_id):
        raise HTTPException(status_code=400, detail="Cannot friend yourself")

    target = db.query(User).filter(User.id == target_user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # If there's an incoming pending request from target -> current user, auto-accept it
    reverse = db.query(FriendRequest).filter(
        FriendRequest.requester_id == target_user_id,
        FriendRequest.addressee_id == current_user.id,
        FriendRequest.status == "PENDING",
    ).with_for_update().first()

    if reverse:
        reverse.status = "ACCEPTED"
        reverse.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {"success": True, "message": "Friend request accepted (auto)"}

    existing = db.query(FriendRequest).filter(
        FriendRequest.requester_id == current_user.id,
        FriendRequest.addressee_id == target_user_id,
    ).first()

    if existing:
        return {"success": True, "message": f"Request already {existing.status.lower()}"}

    fr = FriendRequest(
        requester_id=str(current_user.id),
        addressee_id=str(target_user_id),
        status="PENDING",
    )
    db.add(fr)
    db.commit()
    db.refresh(fr)

    return {"success": True, "message": "Friend request sent", "requestId": str(fr.id)}


@router.post("/accept/{request_id}")
def accept_friend_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fr = db.query(FriendRequest).filter(FriendRequest.id == request_id).with_for_update().first()
    if not fr:
        raise HTTPException(status_code=404, detail="Friend request not found")

    if str(fr.addressee_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not allowed")

    if fr.status != "PENDING":
        return {"success": True, "message": f"Already {fr.status.lower()}"}

    fr.status = "ACCEPTED"
    fr.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"success": True, "message": "Friend request accepted"}


@router.post("/reject/{request_id}")
def reject_friend_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fr = db.query(FriendRequest).filter(FriendRequest.id == request_id).with_for_update().first()
    if not fr:
        raise HTTPException(status_code=404, detail="Friend request not found")

    if str(fr.addressee_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not allowed")

    if fr.status != "PENDING":
        return {"success": True, "message": f"Already {fr.status.lower()}"}

    fr.status = "REJECTED"
    fr.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"success": True, "message": "Friend request rejected"}


@router.get("/requests/incoming")
def incoming_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reqs = db.query(FriendRequest).filter(
        FriendRequest.addressee_id == current_user.id,
        FriendRequest.status == "PENDING",
    ).order_by(FriendRequest.created_at.desc()).all()

    users_map = {}
    out = []

    for r in reqs:
        if r.requester_id not in users_map:
            users_map[r.requester_id] = db.query(User).filter(User.id == r.requester_id).first()
        requester = users_map[r.requester_id]
        addressee = current_user

        out.append({
            "id": str(r.id),
            "status": r.status,
            "createdAt": r.created_at,
            "requester": _mini(requester) if requester else None,
            "addressee": _mini(addressee),
        })

    return {"success": True, "data": out}


@router.get("/requests/outgoing")
def outgoing_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reqs = db.query(FriendRequest).filter(
        FriendRequest.requester_id == current_user.id,
        FriendRequest.status == "PENDING",
    ).order_by(FriendRequest.created_at.desc()).all()

    users_map = {}
    out = []

    for r in reqs:
        if r.addressee_id not in users_map:
            users_map[r.addressee_id] = db.query(User).filter(User.id == r.addressee_id).first()
        addressee = users_map[r.addressee_id]

        out.append({
            "id": str(r.id),
            "status": r.status,
            "createdAt": r.created_at,
            "requester": _mini(current_user),
            "addressee": _mini(addressee) if addressee else None,
        })

    return {"success": True, "data": out}


@router.get("", response_model=FriendsListResponse)
def get_friends(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accepted = db.query(FriendRequest).filter(
        FriendRequest.status == "ACCEPTED",
        or_(
            FriendRequest.requester_id == current_user.id,
            FriendRequest.addressee_id == current_user.id,
        ),
    ).all()

    friend_ids = []
    for r in accepted:
        other = r.addressee_id if str(r.requester_id) == str(current_user.id) else r.requester_id
        friend_ids.append(other)

    if not friend_ids:
        return {"success": True, "data": []}

    friends = db.query(User).filter(User.id.in_(friend_ids)).all()
    data = [_mini(u) for u in friends]

    return {"success": True, "data": data}
