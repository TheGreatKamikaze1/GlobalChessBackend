from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from uuid import UUID

class CreateChallengeSchema(BaseModel):
    stake: float = Field(..., gt=0, description="The amount staked in the challenge.")
    time_control: str = Field(
        "60/0",
        description="Time control format (e.g., '60/0' for 60 minutes no increment)."
    )
    color: str = Field(
        "auto",
        description="Preferred color: 'white', 'black', or 'auto'.",
        pattern="^(white|black|auto)$"
    )


class UserMini(BaseModel):
    id: UUID
    username: str
    displayName: str

    model_config = {
        "from_attributes": True
    }


class ChallengeBase(BaseModel):
    id: UUID
    creatorId: UUID
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
