from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict


class PlayerDetails(BaseModel):
    id: str
    username: str
    displayName: str


class MoveRequest(BaseModel):
    move: str = Field(..., description="Move in UCI format (e.g., 'e2e4' or 'e7e8q')")


class PaginationParams(BaseModel):
    limit: int = Field(10, le=100)
    offset: int = Field(0, ge=0)


class GameResponse(BaseModel):
    id: str
    white: PlayerDetails
    black: PlayerDetails
    stake: float
    status: str
    moves: List[str]
    currentFen: str
    startedAt: datetime
    result: Optional[str] = None
    completedAt: Optional[datetime] = None


class MoveResponse(BaseModel):
    gameId: str
    move: str
    currentFen: str
    isCheck: bool
    isCheckmate: bool
    isGameOver: bool


class ResignResponse(BaseModel):
    gameId: str
    result: str
    winnerId: str
    message: str


class GameHistoryItem(BaseModel):
    id: str
    opponent: PlayerDetails
    stake: float
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
    status: str
    startedAt: datetime
    currentTurn: str  # 'white' or 'black'


class ActiveGamesResponse(BaseModel):
    success: bool = True
    data: List[ActiveGameItem]
