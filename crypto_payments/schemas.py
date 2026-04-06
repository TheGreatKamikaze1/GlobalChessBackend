from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CryptoAssetConfigOut(BaseModel):
    symbol: str
    name: str
    contractAddress: str
    decimals: int
    usdPrice: str


class CryptoNetworkConfigOut(BaseModel):
    key: str
    name: str
    chainId: int
    chainIdHex: str
    currencySymbol: str
    publicRpcUrl: str
    explorerUrl: str
    treasuryAddress: Optional[str] = None
    configured: bool
    assets: List[CryptoAssetConfigOut]


class CryptoConfigData(BaseModel):
    defaultNetwork: str
    defaultAsset: str
    networks: List[CryptoNetworkConfigOut]


class CryptoConfigResponse(BaseModel):
    success: bool = True
    data: CryptoConfigData


class CreateCryptoGiftCheckoutRequest(BaseModel):
    recipientUsername: str = Field(..., min_length=3, max_length=30)
    giftId: str = Field(..., min_length=1, max_length=64)
    note: Optional[str] = Field(default=None, max_length=280)
    network: str = Field(default="BASE", min_length=1, max_length=32)
    asset: str = Field(default="USDC", min_length=1, max_length=16)


class SubmitCryptoPaymentRequest(BaseModel):
    txHash: str = Field(..., min_length=66, max_length=80)
    fromAddress: Optional[str] = Field(default=None, min_length=42, max_length=42)


class CryptoGiftPreview(BaseModel):
    id: str
    name: str
    piece: str
    description: str
    priceUsd: float


class EvmTransactionOut(BaseModel):
    chainIdHex: str
    to: str
    value: str
    data: str


class CryptoGiftCheckoutData(BaseModel):
    reference: str
    status: str
    network: str
    asset: str
    amountUsd: float
    amountCrypto: str
    recipientUsername: str
    note: Optional[str] = None
    treasuryAddress: str
    explorerUrl: str
    tokenContractAddress: str
    tokenDecimals: int
    tokenName: str
    paymentTransaction: EvmTransactionOut
    gift: CryptoGiftPreview


class CryptoGiftCheckoutResponse(BaseModel):
    success: bool = True
    data: CryptoGiftCheckoutData


class CryptoRequestGiftOut(BaseModel):
    id: str
    name: str
    recipientUsername: str
    note: Optional[str] = None
    transferId: Optional[str] = None


class CryptoRequestOut(BaseModel):
    id: str
    reference: str
    kind: str
    status: str
    asset: Optional[str] = None
    network: Optional[str] = None
    walletAddress: Optional[str] = None
    amountUsd: float
    amountCrypto: Optional[str] = None
    txHash: Optional[str] = None
    explorerUrl: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    confirmedAt: Optional[datetime] = None
    linkedGiftTransferId: Optional[str] = None
    gift: Optional[CryptoRequestGiftOut] = None
    detail: Optional[str] = None


class CryptoRequestResponse(BaseModel):
    success: bool = True
    data: CryptoRequestOut


class CryptoRequestListResponse(BaseModel):
    success: bool = True
    data: List[CryptoRequestOut]
