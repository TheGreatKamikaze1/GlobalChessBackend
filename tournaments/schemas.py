from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from typing import Dict, Any


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
    max_players: int = Field(default=64, ge=2)
    format: str = Field(default="Swiss")
    rounds: int = Field(default=7, ge=1)


class TournamentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str
    entry_fee: float
    start_time: datetime
    duration_minutes: int
    deposit_required: bool

    time_control: str
    max_players: int
    format: str
    rounds: int




class JoinTournamentResponse(BaseModel):
    tournament_id: str
    user_id: str
    paid: bool


class FinishTournamentPayload(BaseModel):
    results: List[str]  # ordered list of user_ids by rank


class PrizeItem(BaseModel):
    place: str
    amount: float

class ParticipantItem(BaseModel):
    id: str
    username: str
    wins: int
    losses: int
    score: int
    paid: bool

class MatchItem(BaseModel):
    id: str
    round: int
    white_id: str
    black_id: str
    white: str
    black: str
    status: str
    result: Optional[str] = None

class TournamentDetailsResponse(BaseModel):
    id: str
    creator_id: str
    name: str
    description: Optional[str] = None
    status: str

    players: int
    max_players: int

    prizePool: float
    entryFee: float

    startDate: datetime
    timeControl: str
    format: str
    rounds: int
    duration_minutes: int

    prize_rules: Dict[str, Any]
    prizes: List[PrizeItem]
    participants: List[ParticipantItem]
    matches: List[MatchItem]
