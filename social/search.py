from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from core.database import get_db
from core.models import User, FriendRequest
from core.auth import get_current_user
from social.schemas import SearchUsersResponse, SearchUserOut

router = APIRouter(prefix="/api/search", tags=["Search"])


def _friend_status(db: Session, me_id: str, other_id: str) -> str:
    rel = db.query(FriendRequest).filter(
        or_(
            and_(FriendRequest.requester_id == me_id, FriendRequest.addressee_id == other_id),
            and_(FriendRequest.requester_id == other_id, FriendRequest.addressee_id == me_id),
        )
    ).order_by(FriendRequest.created_at.desc()).first()

    if not rel:
        return "none"
    if rel.status == "ACCEPTED":
        return "friends"
    if rel.status == "PENDING":
        return "outgoing" if str(rel.requester_id) == str(me_id) else "incoming"
    return "none"


@router.get("/users", response_model=SearchUsersResponse)
def search_users(
    q: str = Query(
        ...,
        min_length=1,
        description="Search term (username or display name)",
        examples=["nze", "hasel", "global"],
    ),
    limit: int = Query(
        20,
        ge=1,
        le=50,
        description="Number of results to return (1-50)",
        examples=[20],
    ),
    offset: int = Query(
        0,
        ge=0,
        description="How many results to skip (pagination)",
        examples=[0],
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  
):
    me_id = str(current_user.id)

    base = db.query(User).filter(
        or_(
            User.username.ilike(f"%{q}%"),
            User.display_name.ilike(f"%{q}%"),
        )
    )

    total = base.count()

    users = (
        base.order_by(User.username.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    data = []
    for u in users:
        other_id = str(u.id)
        status = "friends" if other_id == me_id else _friend_status(db, me_id, other_id)

        data.append(
            SearchUserOut(
                id=other_id,
                username=u.username,
                displayName=u.display_name,
                avatarUrl=u.avatar_url,
                rating=u.current_rating or 1200,
                friendStatus=status,
            )
        )

    return {
        "success": True,
        "data": data,
        "pagination": {"total": total, "limit": limit, "offset": offset},
    }
