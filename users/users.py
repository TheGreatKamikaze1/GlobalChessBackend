from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from core.database import get_db
from core.models import User
from users.users_schema import (
    UpdateProfileSchema,
    ProfileResponse,
    MeResponse,
    UpdateProfileResponse,
    BalanceResponse,
    AuthStatusResponse,
)
from core.auth import get_current_user_id

router = APIRouter(tags=["Users"])


def norm_email(email: str) -> str:
    return email.strip().lower()


def norm_username(username: str) -> str:
    return username.strip()


@router.get("/me", response_model=MeResponse)
def get_current_user(
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
            "username": user.username,
            "name": user.name,
            "bio": user.bio,
            "displayName": user.display_name,
            "avatarUrl": user.avatar_url,
            "balance": float(user.balance or 0),
            "rating": user.current_rating or 1200,
            "createdAt": user.created_at,
            "updatedAt": user.updated_at,
        },
    }


@router.get("/profile", response_model=ProfileResponse)
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
            "username": user.username,
            "name": user.name,
            "bio": user.bio,
            "email": user.email,
            "displayName": user.display_name,
            "balance": float(user.balance or 0),
            "rating": user.current_rating or 0,
        },
    }


@router.put("/profile", response_model=UpdateProfileResponse)
def update_profile(
    data: UpdateProfileSchema,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Collision checks (prevents 500s)
    if data.email is not None:
        new_email = norm_email(str(data.email))
        exists = db.query(User).filter(User.email == new_email, User.id != user_id).first()
        if exists:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = new_email

    if data.username is not None:
        new_username = norm_username(data.username)
        exists = db.query(User).filter(User.username == new_username, User.id != user_id).first()
        if exists:
            raise HTTPException(status_code=400, detail="Username already taken")
        user.username = new_username

    if data.name is not None:
        user.name = data.name
    if data.bio is not None:
        user.bio = data.bio
    if data.displayName is not None:
        user.display_name = data.displayName.strip()
    if data.avatarUrl is not None:
        user.avatar_url = data.avatarUrl

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Update violates a unique constraint")

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

    return {
        "success": True,
        "data": {
            "balance": float(user.balance or 0),
            "currency": "NGN",
        },
    }


@router.get("/auth-status", response_model=AuthStatusResponse)
def auth_status(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {
        "success": True,
        "data": {
            "authenticated": True,
            "userId": user.id,
            "email": user.email,
        },
    }
