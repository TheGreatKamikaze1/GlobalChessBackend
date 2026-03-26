from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Literal


class PlayerDetails(BaseModel):
    id: str
    username: str
    displayName: str
    rating: int = 1200


class RatingState(BaseModel):
    isRated: bool
    ratingCategory: str
    timeControl: str
    applied: bool = False
    whiteBefore: Optional[int] = None
    blackBefore: Optional[int] = None
    whiteAfter: Optional[int] = None
    blackAfter: Optional[int] = None
    whiteChange: Optional[int] = None
    blackChange: Optional[int] = None


class MoveRequest(BaseModel):
    move: str = Field(
        ...,
        description=(
            "Move in UCI (e.g. 'e2e4', 'e7e8q') OR SAN (e.g. 'e4', 'Nf3', 'O-O'). "
            "Backend auto-detects."
        ),
    )

class PremoveRequest(BaseModel):
    move: Optional[str] = Field(
        default=None,
        description="UCI move like 'e2e4'. Send null or empty to cancel premove."
    )


class GameResponse(BaseModel):
    id: str
    white: PlayerDetails
    black: PlayerDetails
    stake: float
    timeControl: str
    isRated: bool
    ratingCategory: str
    rating: RatingState
    status: str
    moves: List[str]              
    currentFen: str
    startedAt: datetime
    currentTurn: Literal["white", "black"]
    result: Optional[str] = None
    completedAt: Optional[datetime] = None


class MoveResponse(BaseModel):
    gameId: str
    uci: str
    san: str
    currentFen: str
    isCheck: bool
    isCheckmate: bool
    isGameOver: bool
    rating: Optional[RatingState] = None
    result: Optional[str] = None
    winnerId: Optional[str] = None


class ResignResponse(BaseModel):
    gameId: str
    result: str
    winnerId: str
    message: str
    rating: Optional[RatingState] = None


class GameHistoryItem(BaseModel):
    id: str
    opponent: PlayerDetails
    stake: float
    timeControl: str
    isRated: bool
    ratingCategory: str
    playerRatingBefore: Optional[int] = None
    playerRatingAfter: Optional[int] = None
    playerRatingChange: Optional[int] = None
    result: str
    moveCount: int
    completedAt: datetime


class PaginatedHistory(BaseModel):
    success: bool = True
    data: List[GameHistoryItem]
    pagination: Dict[str, int]


class ActiveGameItem(BaseModel):
    id: str
    opponent: PlayerDetails
    stake: float
    timeControl: str
    isRated: bool
    ratingCategory: str
    status: str
    startedAt: datetime
    currentTurn: Literal["white", "black"]


class ActiveGamesResponse(BaseModel):
    success: bool = True
    data: List[ActiveGameItem]
