

from pydantic import BaseModel, EmailStr

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    username: str
    displayName: str

   
    model_config = {"from_attributes": True}

    class Config:
        orm_mode = True
