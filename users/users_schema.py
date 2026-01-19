from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UpdateProfileSchema(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(default=None, min_length=3, max_length=30)
    bio: Optional[str] = Field(default=None, max_length=500)
    displayName: Optional[str] = Field(default=None, min_length=2, max_length=50)
    avatarUrl: Optional[str] = Field(default=None, max_length=500)


class ProfileData(BaseModel):
    id: str
    email: EmailStr
    username: str
    name: Optional[str] = None
    bio: Optional[str] = None
    displayName: Optional[str] = None
    balance: float
    rating: int


class ProfileResponse(BaseModel):
    success: bool
    data: ProfileData


class MeData(BaseModel):
    id: str
    email: EmailStr
    username: str
    name: Optional[str] = None
    bio: Optional[str] = None
    displayName: Optional[str] = None
    avatarUrl: Optional[str] = None
    balance: float
    rating: int
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class MeResponse(BaseModel):
    success: bool
    data: MeData


class UpdateProfileData(BaseModel):
    id: str
    name: Optional[str] = None
    bio: Optional[str] = None
    displayName: Optional[str] = None
    avatarUrl: Optional[str] = None
    updatedAt: Optional[datetime] = None


class UpdateProfileResponse(BaseModel):
    success: bool
    data: UpdateProfileData


class BalanceData(BaseModel):
    balance: float
    currency: str


class BalanceResponse(BaseModel):
    success: bool
    data: BalanceData


class AuthStatusData(BaseModel):
    authenticated: bool
    userId: str
    email: EmailStr


class AuthStatusResponse(BaseModel):
    success: bool
    data: AuthStatusData
