from pydantic import BaseModel, EmailStr, Field

class RegisterSchema(BaseModel):
    email: EmailStr
    username: str = Field(..., max_length=30)
    displayName: str = Field(..., max_length=50)
    password: str = Field(..., max_length=60)

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    username: str
    displayName: str

    class Config:
        orm_mode = True
