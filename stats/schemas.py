from pydantic import BaseModel
from datetime import datetime
from typing import List


class RecentGame(BaseModel):
    id: str
    opponent: str
    result: str
    stake: float
    completedAt: datetime


class DashboardStats(BaseModel):
    totalGames: int
    wins: int
    losses: int
    draws: int
    winRate: float
    currentBalance: float
    totalEarnings: float
    currentRating: int
    recentGames: List[RecentGame]


class DashboardResponse(BaseModel):
    success: bool = True
    data: DashboardStats
