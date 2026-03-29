from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class GiftCatalogItemOut(BaseModel):
    id: str
    name: str
    piece: str
    description: str
    priceUsd: float


class GiftUserMini(BaseModel):
    id: str
    username: str
    displayName: str
    avatarUrl: Optional[str] = None


class GiftRecordOut(BaseModel):
    id: str
    giftId: str
    giftName: str
    piece: str
    priceUsd: float
    note: Optional[str] = None
    status: str
    redemptionStatus: Optional[str] = None
    purchaseReference: Optional[str] = None
    redemptionReference: Optional[str] = None
    createdAt: datetime
    redeemedAt: Optional[datetime] = None
    sender: GiftUserMini
    recipient: GiftUserMini


class GiftCatalogResponse(BaseModel):
    success: bool = True
    data: List[GiftCatalogItemOut]


class GiftListResponse(BaseModel):
    success: bool = True
    data: List[GiftRecordOut]


class GiftSummaryData(BaseModel):
    sentCount: int
    receivedCount: int
    redeemedCount: int
    pendingSettlements: int
    canGift: bool
    canRedeem: bool


class GiftSummaryResponse(BaseModel):
    success: bool = True
    data: GiftSummaryData


class GiftRecordResponse(BaseModel):
    success: bool = True
    data: GiftRecordOut


class SendGiftRequest(BaseModel):
    recipientUsername: str = Field(..., min_length=3, max_length=30)
    giftId: str = Field(..., min_length=1, max_length=64)
    note: Optional[str] = Field(default=None, max_length=280)
