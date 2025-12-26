from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Optional, List

class DepositRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    paymentMethod: str
    reference: str


class AccountDetails(BaseModel):
    bankName: str
    accountNumber: str


class WithdrawRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    accountDetails: AccountDetails


class TransactionData(BaseModel):
    transactionId: str
    amount: Decimal
    newBalance: Decimal
    status: str
    createdAt: str


class TransactionResponse(BaseModel):
    success: bool
    data: TransactionData


class TransactionHistoryItem(BaseModel):
    id: str
    amount: Decimal
    type: str
    reference: Optional[str]
    status: str
    createdAt: str


class TransactionHistoryResponse(BaseModel):
    success: bool
    data: List[TransactionHistoryItem]
    pagination: dict
