from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError

from core.database import get_db
from core.models import User
from users.auth_schema import RegisterSchema, LoginSchema
from core.auth import create_token

router = APIRouter(tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
BCRYPT_MAX_BYTES = 72


def normalize_password(password: str) -> bytes:
   
    return password.encode("utf-8")[:BCRYPT_MAX_BYTES]


def norm_email(email: str) -> str:
    return email.strip().lower()


def norm_username(username: str) -> str:
    return username.strip()


def norm_display_name(name: str) -> str:
    return name.strip()


@router.post("/register")
def register(req: RegisterSchema, db: Session = Depends(get_db)):
    email = norm_email(req.email)
    username = norm_username(req.username)
    display_name = norm_display_name(req.displayName)

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="User already exists")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    hashed_pw = pwd_context.hash(normalize_password(req.password))

    new_user = User(
        email=email,
        username=username,
        display_name=display_name,
        name=req.name,
        bio=req.bio,
        password=hashed_pw,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        
        db.rollback()
        raise HTTPException(status_code=400, detail="Email or username already in use")

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
    email = norm_email(req.email)

    user = db.query(User).filter(User.email == email).first()
    if not user:
        
        raise HTTPException(status_code=401, detail="Invalid credentials")

    ok = pwd_context.verify(normalize_password(req.password), user.password)
    if not ok:
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
