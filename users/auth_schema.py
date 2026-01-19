from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class RegisterSchema(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=30)
    displayName: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=128)

    name: Optional[str] = Field(default=None, max_length=100)
    bio: Optional[str] = Field(default=None, max_length=500)


class LoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
