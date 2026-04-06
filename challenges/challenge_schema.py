from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Literal


class CreateChallengeSchema(BaseModel):
    stake: float = Field(0, ge=0, description="Legacy field. Staked matches are no longer supported.")
    time_control: str = Field(
        "5+0",
        description="Time control format (e.g., '5+0' for a 5 minute game with no increment).",
    )
    color: Literal["white", "black", "auto"] = Field(
        "auto",
        description="Preferred color: 'white', 'black', or 'auto'.",
    )
    rated: bool = Field(True, description="Whether this challenge should affect player ratings.")


class MatchmakeResponseData(BaseModel):
    matched: bool
    status: Literal["MATCHED", "QUEUED"]
    challengeId: str
    gameId: Optional[str] = None
    message: str
    createdAt: datetime
    expiresAt: datetime
    timeControl: str
    isRated: bool
    ratingCategory: str


class MatchmakeResponse(BaseModel):
    success: bool = True
    data: MatchmakeResponseData


class UserMini(BaseModel):
    id: str
    username: str
    displayName: str
    rating: int = 1200

    model_config = {"from_attributes": True}


class ChallengeBase(BaseModel):
    id: str
    creatorId: str
    stake: float
    timeControl: str
    isRated: bool
    ratingCategory: str
    status: str
    createdAt: datetime
    expiresAt: datetime

    model_config = {"from_attributes": True}


class AvailableChallenge(ChallengeBase):
    creator: UserMini


class MyChallenge(ChallengeBase):
    acceptor: Optional[UserMini] = None


class ChallengeList(BaseModel):
    success: bool = True
    data: List[AvailableChallenge]
    pagination: Dict[str, int]
