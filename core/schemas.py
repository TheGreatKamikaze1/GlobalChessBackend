from pydantic import BaseModel, EmailStr

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    username: str
    displayName: str

    class Config:
        orm_mode = True
