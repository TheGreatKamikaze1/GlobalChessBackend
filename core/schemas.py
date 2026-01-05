from pydantic import BaseModel, EmailStr

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str
    displayName: str

    class Config:
        orm_mode = True
