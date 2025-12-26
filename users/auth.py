from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import jwt
import os
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from db import get_db, User 
from auth_schema import RegisterSchema, LoginSchema  

JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key")

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return user

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def create_token(data: dict):
    payload = {
        **data,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")



@router.post("/register")
def register(req: RegisterSchema, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="User already exists")
    
    hashed_pw = pwd_context.hash(req.password)

    new_user = User(
        email=req.email,
        username=req.username,
        displayName=req.displayName, 
        password=hashed_pw
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_token({"id": new_user.id, "email": new_user.email})
    return {"success": True, "data": {"user": {"id": new_user.id}, "token": token}}



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
