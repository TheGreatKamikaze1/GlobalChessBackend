from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import jwt
import os
from datetime import datetime, timedelta

from db import get_db, User 
from auth_schema import RegisterSchema, LoginSchema  

JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key")

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_token(data: dict):
    payload = {
        **data,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


@router.post("/register")
def register(req: RegisterSchema, db: Session = Depends(get_db)):
    # Check if user exists
    existing_user = db.query(User).filter(User.email == req.email).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail={"success": False, "error": {"code": "USER_EXISTS", "message": "User already exists"}}
        )
    
    
    hashed_pw = pwd_context.hash(req.password)

    # Create user
    new_user = User(
        email=req.email,
        username=req.username,
        display_name=req.displayName,
        password=hashed_pw,
        balance=0
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate token
    token = create_token({"id": new_user.id, "email": new_user.email})

    return {
        "success": True,
        "data": {
            "user": {
                "id": new_user.id,
                "email": new_user.email,
                "username": new_user.username,
                "displayName": new_user.display_name
            },
            "token": token
        }
    }


@router.post("/login")
def login(req: LoginSchema, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=401, detail={"success": False, "error": {"code": "INVALID_CREDENTIALS", "message": "Invalid credentials"}})
    
    # Verify password
    valid = pwd_context.verify(req.password, user.password)
    if not valid:
        raise HTTPException(status_code=401, detail={"success": False, "error": {"code": "INVALID_CREDENTIALS", "message": "Invalid credentials"}})

    # Generate token
    token = create_token({"id": user.id, "email": user.email})

    return {
        "success": True,
        "data": {
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "displayName": user.display_name
            },
            "token": token
        }
    }
