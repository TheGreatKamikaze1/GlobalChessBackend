from fastapi import Depends, HTTPException
from uuid import UUID

from core.auth import get_current_user_id


def get_current_user_id_dep(user_id: str = Depends(get_current_user_id)) -> str:
    try:
       
        UUID(str(user_id))
        return str(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user id in token")
