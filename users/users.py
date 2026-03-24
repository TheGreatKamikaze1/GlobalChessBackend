from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user_id
from core.database import get_db
from core.models import GiftTransfer, User
from premium.service import get_membership_payload
from users.users_schema import (
    AuthStatusResponse,
    BalanceResponse,
    MeResponse,
    ProfileResponse,
    UpdateProfileResponse,
    UpdateProfileSchema,
)

router = APIRouter(tags=["Users"])


class PublicUserData(BaseModel):
    id: str
    username: str
    displayName: Optional[str] = None
    bio: Optional[str] = None
    avatarUrl: Optional[str] = None
    rating: int
    createdAt: Optional[datetime] = None
    isPremium: bool = False
    membershipTier: str = "standard"


class PublicUserResponse(BaseModel):
    success: bool = True
    data: PublicUserData


def _gift_counts(db: Session, user_id: str) -> dict:
    sent_count = db.query(GiftTransfer).filter(GiftTransfer.sender_id == user_id).count()
    received_count = db.query(GiftTransfer).filter(GiftTransfer.recipient_id == user_id).count()
    return {
        "sentGiftCount": sent_count,
        "receivedGiftCount": received_count,
    }


def _profile_payload(db: Session, user: User) -> dict:
    membership = get_membership_payload(db, str(user.id))
    gift_counts = _gift_counts(db, str(user.id))

    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "name": user.name,
        "bio": user.bio,
        "displayName": user.display_name,
        "avatarUrl": user.avatar_url,
        "balance": 0.0,
        "rating": user.current_rating or 1200,
        "createdAt": user.created_at,
        "updatedAt": user.updated_at,
        **membership,
        **gift_counts,
    }


@router.get("/me", response_model=MeResponse)
def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"success": True, "data": _profile_payload(db, user)}


@router.get("/profile", response_model=ProfileResponse)
def get_profile(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"success": True, "data": _profile_payload(db, user)}


@router.put("/profile", response_model=UpdateProfileResponse)
def update_profile(
    data: UpdateProfileSchema,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.name is not None:
        user.name = data.name
    if data.email is not None:
        user.email = data.email
    if data.username is not None:
        user.username = data.username
    if data.bio is not None:
        user.bio = data.bio
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
            "name": user.name,
            "bio": user.bio,
            "displayName": user.display_name,
            "avatarUrl": user.avatar_url,
            "updatedAt": user.updated_at,
        },
    }


@router.get("/balance", response_model=BalanceResponse)
def get_balance(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"success": True, "data": {"balance": 0.0, "currency": "USD"}}


@router.get("/auth-status", response_model=AuthStatusResponse)
def auth_status(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {"success": True, "data": {"authenticated": True, "userId": user.id, "email": user.email}}


@router.get("/{user_id}", response_model=PublicUserResponse)
def get_user_by_id(
    user_id: str,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    membership = get_membership_payload(db, user_id)

    return {
        "success": True,
        "data": {
            "id": str(user.id),
            "username": user.username,
            "displayName": user.display_name,
            "bio": user.bio,
            "avatarUrl": user.avatar_url,
            "rating": user.current_rating or 1200,
            "createdAt": user.created_at,
            "isPremium": membership["isPremium"],
            "membershipTier": membership["membershipTier"],
        },
    }
