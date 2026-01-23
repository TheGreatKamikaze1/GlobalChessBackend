from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


class DepositRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    reference: Optional[str] = None


class WithdrawRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)

    bank_code: str = Field(..., min_length=3, max_length=10)
    account_number: str = Field(..., min_length=10, max_length=10)


    account_name: str = Field(..., min_length=2)

    password: str = Field(..., min_length=1)

    reason: Optional[str] = None
    reference: Optional[str] = None



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

class BankItem(BaseModel):
    name: str
    code: str
    slug: Optional[str] = None
    longcode: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    type: Optional[str] = None


class BanksResponse(BaseModel):
    success: bool = True
    data: List[BankItem]


class ResolveAccountData(BaseModel):
    account_name: str
    account_number: str
    bank_code: str


class ResolveAccountResponse(BaseModel):
    success: bool = True
    data: ResolveAccountData
