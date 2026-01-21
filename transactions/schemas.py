from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


class DepositRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    reference: Optional[str] = None


class WithdrawRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)

    # Paystack transfer destination (NUBAN)
    bank_code: str = Field(..., min_length=2, max_length=10, description="Paystack bank code e.g. 058")
    account_number: str = Field(..., min_length=10, max_length=10, description="NUBAN account number (10 digits)")

  
    reason: Optional[str] = Field(default="Wallet withdrawal")
    reference: Optional[str] = Field(default=None, description="Optional idempotency reference")

    password: str = Field(..., min_length=6, description="User password confirmation")


class TransactionData(BaseModel):
    transactionId: str
    amount: Decimal
    newBalance: Optional[Decimal] = None
    type: Optional[str] = None
    reference: Optional[str] = None
    status: str
    createdAt: datetime

   
    payoutStatus: Optional[str] = None
    transferCode: Optional[str] = None
    accountName: Optional[str] = None


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
