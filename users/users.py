from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import User
from users.users_schema import UpdateProfileSchema  
from core.auth import get_current_user_id

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/profile")
def get_profile(
    user_id: int = Depends(get_current_user_id),
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
            "displayName": user.displayName,
            "balance": float(user.balance or 0),
            "rating": user.currentRating or 0,
        },
    }


@router.put("/profile")
def update_profile(
    data: UpdateProfileSchema,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.displayName is not None:
        user.displayName = data.displayName

    if data.avatarUrl is not None:
        user.avatarUrl = data.avatarUrl

    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "data": {
            "id": user.id,
            "displayName": user.displayName,
            "avatarUrl": user.avatarUrl,
            "updatedAt": user.updatedAt,
        },
    }


@router.get("/balance")
def get_balance(
    user_id: int = Depends(get_current_user_id),
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
