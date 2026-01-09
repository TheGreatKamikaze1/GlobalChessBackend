from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional


class PrizeRule(BaseModel):
    places: List[int]  # [1,2,3]
    distribution: List[float]  # [0.5, 0.3, 0.2]


class TournamentCreate(BaseModel):
    name: str
    description: Optional[str]
    entry_fee: float = Field(ge=0)
    deposit_required: bool
    prize_rules: PrizeRule
    time_control: str
    start_time: datetime
    duration_minutes: int


class TournamentResponse(BaseModel):
    id: str
    name: str
    status: str
    entry_fee: float
    start_time: datetime
    duration_minutes: int
    deposit_required: bool


class JoinTournamentResponse(BaseModel):
    tournament_id: str
    user_id: str
    paid: bool


class FinishTournamentPayload(BaseModel):
    results: List[str]  # ordered list of user_ids by rank
