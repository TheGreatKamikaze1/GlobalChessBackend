from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class RegisterSchema(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3)
    displayName: str = Field(min_length=2)
    password: str = Field(min_length=6)

    name: Optional[str] = None
    bio: Optional[str] = None
class LoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
