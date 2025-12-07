import jwt
import os
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from db import get_db, User 

JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key")

def get_current_user(
    db: Session = Depends(get_db),
    Authorization: str = Header(None)
):
    """
    Decodes the JWT from the 'Authorization: Bearer <token>' header
    and fetches the user object.
    """
    if not Authorization or not Authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"success": False, "error": {"code": "UNAUTHORIZED", "message": "Unauthorized"}}
        )

    token = Authorization.split(" ")[1]

    try:
        #decode token
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("id")

        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail={"success": False, "error": {"code": "UNAUTHORIZED", "message": "Unauthorized: Invalid token payload"}}
            )

        #check for user existence
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(
                status_code=401,
                detail={"success": False, "error": {"code": "UNAUTHORIZED", "message": "Unauthorized: User not found"}}
            )
            
        return user 
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "error": {"code": "UNAUTHORIZED", "message": "Unauthorized: Token has expired"}}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "error": {"code": "UNAUTHORIZED", "message": "Unauthorized: Invalid token"}}
        )


def get_current_user_id(user: User = Depends(get_current_user)) -> int:
    return user.id