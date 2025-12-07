from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

#  Input Schemas 

class CreateChallengeSchema(BaseModel):
    
    stake: float = Field(..., gt=0, description="The amount staked in the challenge.")

# nested Schemas for Output

class UserMini(BaseModel):
    id: int
    username: str
    displayName: str

    class Config:
        
        from_attributes = True
       
        alias_generator = lambda string: string.replace('_', '').replace('displayname', 'displayName')
        populate_by_name = True



    
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
        alias_generator = lambda string: string.replace('_', '').replace('creatorid', 'creatorId')
        populate_by_name = True

# schemas for specific endpoints

class AvailableChallenge(ChallengeBase):
    creator: UserMini

class MyChallenge(ChallengeBase):
    acceptor: Optional[UserMini] = None

class ChallengeList(BaseModel):
    success: bool = True
    data: List[AvailableChallenge]
    pagination: dict