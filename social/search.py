from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
from typing import List, Optional, Dict

from core.database import get_db
from core.models import User


router = APIRouter(prefix="/api/search", tags=["Search"])


class SearchUserOut(BaseModel):
    id: str
    username: str
    displayName: str
    avatarUrl: Optional[str] = None
    rating: int


class SearchUsersResponse(BaseModel):
    success: bool = True
    data: List[SearchUserOut]
    pagination: Dict[str, int]


@router.get("/users", response_model=SearchUsersResponse)
def search_users(
    q: str = Query(
        ...,
        min_length=1,
        description="Search term (username or display name)",
        examples={"sample": {"summary": "Example search", "value": "nze"}},
    ),
    limit: int = Query(
        20,
        ge=1,
        le=50,
        description="Number of results to return (1-50)",
        examples={"sample": {"summary": "Example limit", "value": 20}},
    ),
    offset: int = Query(
        0,
        ge=0,
        description="How many results to skip (pagination)",
        examples={"sample": {"summary": "Example offset", "value": 0}},
    ),
    db: Session = Depends(get_db),
):
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

    data = [
        SearchUserOut(
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
