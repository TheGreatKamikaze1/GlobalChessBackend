from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from stats.schemas import DashboardResponse
from stats.stats import get_dashboard_stats
from game_management.dependencies import get_current_user_id

router = APIRouter(tags=["Statistics"])

@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    data = get_dashboard_stats(db, user_id)
    return {
        "success": True,
        "data": data
    }
