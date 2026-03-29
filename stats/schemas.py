from pydantic import BaseModel
from datetime import datetime
from typing import List
from core.rating_schemas import RatingStats


class RecentGame(BaseModel):
    id: str
    opponent: str
    result: str
    stake: float
    timeControl: str
    isRated: bool
    ratingCategory: str
    ratingChange: int | None = None
    completedAt: datetime


class GiftActivity(BaseModel):
    sent: int
    received: int
    redeemed: int


class DashboardStats(BaseModel):
    totalGames: int
    wins: int
    losses: int
    draws: int
    winRate: float
    currentBalance: float
    totalEarnings: float
    currentRating: int
    ratingStats: RatingStats
    giftActivity: GiftActivity
    recentGames: List[RecentGame]


class DashboardResponse(BaseModel):
    success: bool = True
    data: DashboardStats
