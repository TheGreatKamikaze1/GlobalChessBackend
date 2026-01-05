from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class CreateChallengeSchema(BaseModel):
    stake: float = Field(..., gt=0)
    time_control: str = Field("60/0")
    color: str = Field("auto", regex="^(white|black|auto)$")


class UserMini(BaseModel):
    id: int
    username: str
    displayName: str

    class Config:
        from_attributes = True


class ChallengeBase(BaseModel):
    id: int
    creatorId: int
    stake: float
    timeControl: str
    status: str
    createdAt: datetime
    expiresAt: datetime

    class Config:
        from_attributes = True


class AvailableChallenge(ChallengeBase):
    creator: UserMini


class MyChallenge(ChallengeBase):
    acceptor: Optional[UserMini] = None


class ChallengeList(BaseModel):
    success: bool = True
    data: List[AvailableChallenge]
    pagination: dict
