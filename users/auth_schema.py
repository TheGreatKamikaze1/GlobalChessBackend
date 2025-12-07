from pydantic import BaseModel, EmailStr, Field

class RegisterSchema(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3)
    displayName: str = Field(min_length=2)
    password: str = Field(min_length=6)

class LoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
