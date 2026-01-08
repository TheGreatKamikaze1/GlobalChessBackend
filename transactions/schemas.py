from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


class DepositRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    reference: Optional[str] = None


class WithdrawRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)


class TransactionData(BaseModel):
    transactionId: str
    amount: Decimal
    newBalance: Optional[Decimal] = None
    type: Optional[str] = None
    reference: Optional[str] = None
    status: str
    createdAt: datetime


class TransactionResponse(BaseModel):
    success: bool = True
    data: TransactionData


class TransactionHistoryItem(BaseModel):
    id: str
    amount: Decimal
    type: str
    reference: Optional[str]
    status: str
    createdAt: datetime


class TransactionHistoryResponse(BaseModel):
    success: bool = True
    data: List[TransactionHistoryItem]
    pagination: dict
