from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from core.database import get_db
from core.models import User
from users.auth_schema import RegisterSchema, LoginSchema
from core.auth import create_token

router = APIRouter(prefix="/auth", tags=["Auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/register")
def register(req: RegisterSchema, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="User already exists")

    hashed_pw = pwd_context.hash(req.password)

    new_user = User(
        email=req.email,
        username=req.username,
        display_name=req.displayName,
        password=hashed_pw,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_token({"id": new_user.id, "email": new_user.email})

    return {
        "success": True,
        "data": {
            "user": {
                "id": new_user.id,
                "email": new_user.email,
                "username": new_user.username,
                "displayName": new_user.display_name,
            },
            "token": token,
        },
    }


@router.post("/login")
def login(req: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()

    if not user or not pwd_context.verify(req.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({"id": user.id, "email": user.email})

    return {
        "success": True,
        "data": {
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "displayName": user.display_name,
            },
            "token": token,
        },
    }
