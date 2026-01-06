from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import User
from users.users_schema import UpdateProfileSchema
from core.auth import get_current_user_id

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/profile")
def get_profile(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "success": True,
        "data": {
            "id": user.id,
            "email": user.email,
            "displayName": user.display_name,
            "balance": float(user.balance or 0),
            "rating": user.current_rating or 0,
        },
    }


@router.put("/profile")
def update_profile(
    data: UpdateProfileSchema,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.displayName is not None:
        user.display_name = data.displayName

    if data.avatarUrl is not None:
        user.avatar_url = data.avatarUrl

    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "data": {
            "id": user.id,
            "displayName": user.display_name,
            "avatarUrl": user.avatar_url,
            "updatedAt": user.updated_at,
        },
    }


@router.get("/balance")
def get_balance(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "success": True,
        "data": {
            "balance": float(user.balance or 0),
            "currency": "USD",
        },
    }
