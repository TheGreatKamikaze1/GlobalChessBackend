from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from core.database import get_db
from core.models import User
from core.auth import get_current_user
from social.schemas import SearchUsersResponse, UserMiniOut

router = APIRouter(prefix="/api/users", tags=["Search"])


@router.get("/search", response_model=SearchUsersResponse)
def search_users(
    q: str = Query(..., min_length=1, max_length=50),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    term = q.strip()
    pattern = f"%{term}%"

    base = db.query(User).filter(
        User.id != current_user.id,
        or_(
            User.username.ilike(pattern),
            User.display_name.ilike(pattern),
        ),
    )

    total = base.count()
    users = base.order_by(User.username.asc()).offset(offset).limit(limit).all()

    data = [
        UserMiniOut(
            id=str(u.id),
            username=u.username,
            displayName=u.display_name,
            avatarUrl=u.avatar_url,
            rating=u.current_rating or 1200,
        )
        for u in users
    ]

    return {
        "success": True,
        "data": data,
        "pagination": {"total": total, "limit": limit, "offset": offset},
    }
