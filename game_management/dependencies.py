from fastapi import Depends, HTTPException
from core.auth import get_current_user_id


def get_current_user_id_dep(user_id=Depends(get_current_user_id)) -> int:

    try:
        return int(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user id in token")
