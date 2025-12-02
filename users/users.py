from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db import get_db
from models import User
from users_schema import UpdateProfileSchema
from fastapi.security import HTTPBearer
import jwt

JWT_SECRET = "your-secret-key"

router = APIRouter(prefix="/users", tags=["Users"])

security = HTTPBearer()

# decode token and get user id
def get_current_user(token: str = Depends(security)):
    try:
        payload = jwt.decode(token.credentials, JWT_SECRET, algorithms=["HS256"])
        return payload["id"]
    except:
        raise HTTPException(status_code=401, detail="Unauthorized")


#get profile
@router.get("/profile")
def get_profile(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "success": True,
        "data": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "displayName": user.displayName,
            "avatarUrl": user.avatarUrl,
            "balance": user.balance,
            "gamesPlayed": user.gamesPlayed,
            "gamesWon": user.gamesWon,
            "currentRating": user.currentRating,
            "createdAt": user.createdAt,
        },
    }


#updateprofile

@router.put("/profile")
def update_profile(
    data: UpdateProfileSchema,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update fields
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


#get balance

@router.get("/balance")
def get_balance(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "success": True,
        "data": {
            "balance": user.balance,
            "currency": "USD",
        },
    }
