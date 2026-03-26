from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SupportedRail(BaseModel):
    asset: str
    network: str


class PremiumConfigData(BaseModel):
    monthlyFeeUsd: float
    supportedRails: List[SupportedRail]
    features: List[str]


class PremiumConfigResponse(BaseModel):
    success: bool = True
    data: PremiumConfigData


class PremiumMembershipData(BaseModel):
    isPremium: bool
    membershipTier: str
    walletAddress: Optional[str] = None
    preferredAsset: Optional[str] = None
    preferredNetwork: Optional[str] = None
    premiumSince: Optional[datetime] = None
    premiumUntil: Optional[datetime] = None
    giftingEnabled: bool
    monthlyFeeUsd: float
    paymentStatus: str
    cryptoReference: Optional[str] = None


class PremiumMembershipResponse(BaseModel):
    success: bool = True
    data: PremiumMembershipData


class ActivatePremiumRequest(BaseModel):
    walletAddress: str = Field(..., min_length=10, max_length=255)
    asset: str = Field(default="USDT", min_length=2, max_length=32)
    network: str = Field(default="TRC20", min_length=2, max_length=32)
