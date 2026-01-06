from fastapi import Depends
from core.auth import get_current_user_id


def get_current_user_id_dep(
    user_id: str = Depends(get_current_user_id),
) -> str:
    return user_id
