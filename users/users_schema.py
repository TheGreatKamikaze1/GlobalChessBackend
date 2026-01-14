from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime



class UpdateProfileSchema(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    bio: Optional[str] = None
    displayName: Optional[str] = None
    avatarUrl: Optional[str] = None


class ProfileData(BaseModel):
    id: str
    email: EmailStr
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
