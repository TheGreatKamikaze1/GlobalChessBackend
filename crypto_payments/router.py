from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import CryptoRequest, User
from crypto_payments.schemas import (
    CreateCryptoGiftCheckoutRequest,
    CreateCryptoWalletCheckoutRequest,
    CryptoConfigResponse,
    CryptoGiftCheckoutResponse,
    CryptoRequestListResponse,
    CryptoRequestResponse,
    CryptoWalletCheckoutResponse,
    SubmitCryptoPaymentRequest,
)
from crypto_payments.service import (
    build_checkout_response,
    build_crypto_request_payload,
    build_wallet_checkout_response,
    create_gift_checkout,
    create_wallet_checkout,
    mark_request_submitted,
    serialize_supported_networks,
    settle_verified_gift_request,
    settle_verified_wallet_request,
    verify_request_transaction,
)

router = APIRouter(tags=["Crypto"])


@router.get("/config", response_model=CryptoConfigResponse)
def get_crypto_config():
    return {
        "success": True,
        "data": {
            "defaultNetwork": "BASE",
            "defaultAsset": "USDC",
            "networks": serialize_supported_networks(),
        },
    }


@router.get("/requests", response_model=CryptoRequestListResponse)
def list_crypto_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    requests = (
        db.query(CryptoRequest)
        .filter(CryptoRequest.user_id == current_user.id)
        .order_by(CryptoRequest.created_at.desc())
        .limit(25)
        .all()
    )

    return {"success": True, "data": [build_crypto_request_payload(request) for request in requests]}


@router.post("/gifts/checkout", response_model=CryptoGiftCheckoutResponse)
def create_crypto_gift_checkout(
    payload: CreateCryptoGiftCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    request = create_gift_checkout(
        db=db,
        current_user=current_user,
        recipient_username=payload.recipientUsername,
        gift_id=payload.giftId,
        note=payload.note,
        network_key=payload.network,
        asset_symbol=payload.asset,
    )

    return {"success": True, "data": build_checkout_response(request)}


@router.post("/wallets/checkout", response_model=CryptoWalletCheckoutResponse)
def create_crypto_wallet_checkout(
    payload: CreateCryptoWalletCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    request = create_wallet_checkout(
        db=db,
        current_user=current_user,
        amount_usd=payload.amountUsd,
        network_key=payload.network,
        asset_symbol=payload.asset,
    )

    return {"success": True, "data": build_wallet_checkout_response(request)}


def _get_owned_request(db: Session, reference: str, user_id: str) -> CryptoRequest:
    request = (
        db.query(CryptoRequest)
        .filter(CryptoRequest.reference == reference, CryptoRequest.user_id == user_id)
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="Crypto payment request not found")
    return request


@router.post("/requests/{reference}/submit", response_model=CryptoRequestResponse)
async def submit_crypto_payment(
    reference: str,
    payload: SubmitCryptoPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    request = _get_owned_request(db, reference, current_user.id)

    verification = await verify_request_transaction(
        request=request,
        tx_hash=payload.txHash,
        from_address=payload.fromAddress,
    )

    if verification["state"] == "COMPLETED":
        if request.kind == "WALLET_DEPOSIT":
            request = settle_verified_wallet_request(
                db=db,
                request=request,
                from_address=verification["fromAddress"],
                tx_hash=payload.txHash,
                detail=verification["detail"],
            )
        else:
            request = settle_verified_gift_request(
                db=db,
                request=request,
                from_address=verification["fromAddress"],
                tx_hash=payload.txHash,
                detail=verification["detail"],
            )
    else:
        request = mark_request_submitted(
            db=db,
            request=request,
            tx_hash=payload.txHash,
            from_address=payload.fromAddress,
            status="PENDING_CONFIRMATION",
            detail=verification["detail"],
        )

    return {"success": True, "data": build_crypto_request_payload(request)}


@router.post("/requests/{reference}/verify", response_model=CryptoRequestResponse)
async def verify_crypto_payment(
    reference: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    request = _get_owned_request(db, reference, current_user.id)
    meta = request.meta or {}
    tx_meta = meta.get("transaction") or {}
    tx_hash = tx_meta.get("txHash")
    from_address = tx_meta.get("fromAddress")

    if not tx_hash:
        raise HTTPException(status_code=400, detail="No submitted transaction was found for this request")

    verification = await verify_request_transaction(
        request=request,
        tx_hash=tx_hash,
        from_address=from_address,
    )

    if verification["state"] == "COMPLETED":
        if request.kind == "WALLET_DEPOSIT":
            request = settle_verified_wallet_request(
                db=db,
                request=request,
                from_address=verification["fromAddress"],
                tx_hash=tx_hash,
                detail=verification["detail"],
            )
        else:
            request = settle_verified_gift_request(
                db=db,
                request=request,
                from_address=verification["fromAddress"],
                tx_hash=tx_hash,
                detail=verification["detail"],
            )
    else:
        request = mark_request_submitted(
            db=db,
            request=request,
            tx_hash=tx_hash,
            from_address=from_address,
            status="PENDING_CONFIRMATION",
            detail=verification["detail"],
        )

    return {"success": True, "data": build_crypto_request_payload(request)}
