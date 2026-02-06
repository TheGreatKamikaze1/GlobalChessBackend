from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session
from decimal import Decimal
import uuid
import os
from datetime import datetime, timezone

from passlib.context import CryptContext
from pydantic import BaseModel

from core.database import get_db
from core.models import User, Transaction
from transactions.schemas import (
    DepositRequest,
    WithdrawRequest,
    TransactionResponse,
    TransactionHistoryResponse,
    BanksResponse,
    ResolveAccountResponse,
)
from core.auth import get_current_user

from payment_service.app.services.paystack_service import (
    list_banks,
    resolve_account_number,
    create_transfer_recipient,
    initiate_transfer,
    verify_transfer,
)

router = APIRouter(tags=["Transactions"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
BCRYPT_MAX_BYTES = 72


def normalize_password(password: str) -> bytes:
    return password.encode("utf-8")[:BCRYPT_MAX_BYTES]


def _verify_password_or_401(user: User, password: str):
    if not user.password:
        raise HTTPException(status_code=500, detail="User password field missing")
    ok = pwd_context.verify(normalize_password(password), user.password)
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid password")


def _norm_name(s: str) -> str:
    # Normalize whitespace and case for safe comparisons
    return " ".join((s or "").split()).strip().lower()


def _require_internal_paystack(
    x_internal_call: str = Header(None, alias="x-internal-call"),
    x_internal_secret: str = Header(None, alias="x-internal-secret"),
):
    if x_internal_call != "PAYSTACK":
        raise HTTPException(status_code=403, detail="Forbidden")

    secret = os.getenv("INTERNAL_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=500, detail="INTERNAL_WEBHOOK_SECRET is not configured")

    if x_internal_secret != secret:
        raise HTTPException(status_code=403, detail="Forbidden")


class WithdrawalWebhookUpdate(BaseModel):
    reference: str
    status: str  # success | failed | reversed
    transfer_code: str | None = None
    event: str | None = None


@router.post("/deposit", response_model=TransactionResponse)
def deposit_funds(
    payload: DepositRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Idempotency by reference
    if payload.reference:
        existing = db.query(Transaction).filter_by(reference=payload.reference).first()
        if existing:
            if existing.user_id != current_user.id:
                raise HTTPException(status_code=400, detail="Reference already used")

            user = db.query(User).filter(User.id == current_user.id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            return {
                "success": True,
                "data": {
                    "transactionId": str(existing.id),
                    "amount": existing.amount,
                    "newBalance": user.balance,
                    "status": existing.status,
                    "createdAt": existing.created_at.isoformat() if existing.created_at else None,
                },
            }

    user = db.query(User).filter(User.id == current_user.id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.balance = (user.balance or Decimal("0.00")) + payload.amount

    txn = Transaction(
        user_id=current_user.id,
        amount=payload.amount,
        type="DEPOSIT",
        reference=payload.reference,
        status="COMPLETED",
        provider="internal",
        payout_status=None,
        meta=None,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    return {
        "success": True,
        "data": {
            "transactionId": str(txn.id),
            "amount": payload.amount,
            "newBalance": user.balance,
            "status": txn.status,
            "createdAt": txn.created_at.isoformat(),
        },
    }


@router.get("/banks", response_model=BanksResponse)
async def get_all_banks(
    country: str = Query("nigeria"),
    per_page: int = Query(200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
):
    try:
        resp = await list_banks(country=country, per_page=per_page)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Paystack list_banks failed: {str(e)[:300]}")

    banks = resp.get("data") or []

    return {
        "success": True,
        "data": [
            {
                "name": b.get("name"),
                "code": b.get("code"),
                "slug": b.get("slug"),
                "longcode": b.get("longcode"),
                "country": b.get("country"),
                "currency": b.get("currency"),
                "type": b.get("type"),
            }
            for b in banks
            if b.get("name") and b.get("code")
        ],
    }


@router.get("/resolve-account", response_model=ResolveAccountResponse)
async def resolve_account(
    account_number: str = Query(..., min_length=10, max_length=10),
    bank_code: str = Query(..., min_length=3, max_length=10),
    current_user: User = Depends(get_current_user),
):
  
    try:
        resp = await resolve_account_number(account_number=account_number, bank_code=bank_code)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Paystack resolve_account failed: {str(e)[:300]}")

    data = resp.get("data") or {}
    name = data.get("account_name")
    acc = data.get("account_number") or account_number

    if not name:
        raise HTTPException(status_code=400, detail="Could not resolve account name")

    return {
        "success": True,
        "data": {
            "account_name": name,
            "account_number": acc,
            "bank_code": bank_code,
        },
    }


@router.post("/withdraw", response_model=TransactionResponse)
async def withdraw_funds(
    payload: WithdrawRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_password_or_401(current_user, payload.password)

    reference = payload.reference or f"wd_{uuid.uuid4().hex}"

 
    existing = (
        db.query(Transaction)
        .filter_by(user_id=current_user.id, type="WITHDRAWAL", reference=reference)
        .first()
    )
    if existing:
        user = db.query(User).filter(User.id == current_user.id).first()
        return {
            "success": True,
            "data": {
                "transactionId": str(existing.id),
                "amount": existing.amount,
                "newBalance": user.balance if user else None,
                "type": existing.type,
                "reference": existing.reference,
                "status": existing.status,
                "payoutStatus": getattr(existing, "payout_status", None),
                "transferCode": getattr(existing, "transfer_code", None),
                "accountName": getattr(existing, "account_name", None),
                "createdAt": existing.created_at.isoformat() if existing.created_at else None,
            },
        }

    user = (
        db.query(User)
        .filter(User.id == current_user.id)
        .with_for_update()
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.balance is None or user.balance < payload.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")

   
    try:
        resolved = await resolve_account_number(payload.account_number, payload.bank_code)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Paystack resolve_account failed: {str(e)[:300]}")

    resolved_name = (resolved.get("data", {}) or {}).get("account_name")
    if not resolved_name:
        raise HTTPException(status_code=400, detail="Could not resolve account name")

    # IMPORTANT: user must not withdraw unless name has been resolved and matches
    if _norm_name(payload.account_name) != _norm_name(resolved_name):
        raise HTTPException(
            status_code=400,
            detail="Account name mismatch. Please resolve the account again before withdrawing.",
        )

    # Create transfer recipient
    try:
        rcp = await create_transfer_recipient(
            name=resolved_name,
            account_number=payload.account_number,
            bank_code=payload.bank_code,
            currency="NGN",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Paystack create_recipient failed: {str(e)[:300]}")

    recipient_code = (rcp.get("data", {}) or {}).get("recipient_code")
    if not recipient_code:
        raise HTTPException(status_code=502, detail="Recipient creation failed")

    # Deduct wallet + create txn
    user.balance = (user.balance or Decimal("0.00")) - payload.amount
    now = datetime.now(timezone.utc)

    txn = Transaction(
        user_id=current_user.id,
        amount=payload.amount,
        type="WITHDRAWAL",
        reference=reference,
        status="PENDING",

        provider="paystack",
        payout_status="initialized",

        bank_code=payload.bank_code,
        bank_name=None,
        account_name=resolved_name,
        account_number_last4=str(payload.account_number)[-4:],

        recipient_code=recipient_code,
        transfer_code=None,

        withdrawal_reason=payload.reason,
        payout_initiated_at=now,
        payout_completed_at=None,
        payout_event=None,

        meta={
            "resolve_account": resolved.get("data", {}),
            "recipient": (rcp.get("data", {}) or {}),
        },
    )

    db.add(txn)
    db.commit()
    db.refresh(txn)

    # Initiate transfer
    try:
        trf = await initiate_transfer(
            amount_naira=payload.amount,
            recipient_code=recipient_code,
            reference=reference,
            reason=payload.reason,
        )

        paystack_status = (trf.get("data", {}) or {}).get("status")  # pending / otp
        transfer_code = (trf.get("data", {}) or {}).get("transfer_code")

        txn.transfer_code = transfer_code
        txn.payout_status = paystack_status or "pending"
        txn.status = "OTP_REQUIRED" if paystack_status == "otp" else "PROCESSING"

        txn.meta = (txn.meta or {})
        txn.meta["transfer_init"] = (trf.get("data", {}) or {})

        db.commit()

        return {
            "success": True,
            "data": {
                "transactionId": str(txn.id),
                "amount": txn.amount,
                "newBalance": user.balance,
                "type": txn.type,
                "reference": txn.reference,
                "status": txn.status,
                "payoutStatus": txn.payout_status,
                "transferCode": txn.transfer_code,
                "accountName": txn.account_name,
                "createdAt": txn.created_at.isoformat() if txn.created_at else None,
            },
        }

    except Exception as e:
        # Refund wallet + mark failed
        user.balance = (user.balance or Decimal("0.00")) + payload.amount
        txn.status = "FAILED"
        txn.payout_status = "failed"
        txn.payout_completed_at = datetime.now(timezone.utc)
        txn.meta = (txn.meta or {})
        txn.meta["init_error"] = str(e)
        db.commit()

        msg = str(e)
        if "transfer_unavailable" in msg:
            raise HTTPException(
                status_code=400,
                detail="Paystack Transfers is not enabled for this business account (transfer_unavailable). "
                       "Upgrade/verify the Paystack business account to a Registered Business or enable Transfers in Paystack.",
            )

        raise HTTPException(status_code=502, detail=msg)


@router.post("/withdraw/webhook")
def withdraw_webhook_update(
    payload: WithdrawalWebhookUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(_require_internal_paystack),
):
    status = (payload.status or "").lower()
    if status not in ("success", "failed", "reversed"):
        raise HTTPException(status_code=400, detail="Invalid status")

    txn = (
        db.query(Transaction)
        .filter_by(reference=payload.reference, type="WITHDRAWAL")
        .with_for_update()
        .first()
    )
    if not txn:
        return {"status": "not tracked"}

    user = db.query(User).filter(User.id == txn.user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    txn.provider = txn.provider or "paystack"
    txn.payout_status = status
    if payload.transfer_code and not txn.transfer_code:
        txn.transfer_code = payload.transfer_code
    if payload.event:
        txn.payout_event = payload.event

    txn.meta = (txn.meta or {})
    txn.meta["transfer_webhook"] = {
        "status": status,
        "event": payload.event,
        "transfer_code": payload.transfer_code,
    }

    now = datetime.now(timezone.utc)

    if status == "success":
        if txn.status == "COMPLETED":
            if not txn.payout_completed_at:
                txn.payout_completed_at = now
                db.commit()
            return {"status": "already completed"}

        if txn.status in ("FAILED", "REVERSED"):
            db.commit()
            return {"status": "ignored", "reason": "already failed/reversed"}

        txn.status = "COMPLETED"
        txn.payout_completed_at = now
        db.commit()
        return {"status": "completed"}

    if txn.status in ("FAILED", "REVERSED"):
        if not txn.payout_completed_at:
            txn.payout_completed_at = now
            db.commit()
        return {"status": "already finalized"}

    user.balance = (user.balance or Decimal("0.00")) + txn.amount
    txn.status = "REVERSED" if status == "reversed" else "FAILED"
    txn.payout_completed_at = now
    db.commit()
    return {"status": txn.status}


@router.get("/withdraw/verify/{reference}", response_model=TransactionResponse)
async def verify_withdrawal_fallback(
    reference: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    txn = (
        db.query(Transaction)
        .filter_by(user_id=current_user.id, type="WITHDRAWAL", reference=reference)
        .with_for_update()
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Withdrawal transaction not found")

    if txn.status in ("COMPLETED", "FAILED", "REVERSED"):
        user = db.query(User).filter(User.id == current_user.id).first()
        return {
            "success": True,
            "data": {
                "transactionId": str(txn.id),
                "amount": txn.amount,
                "newBalance": user.balance if user else None,
                "type": txn.type,
                "reference": txn.reference,
                "status": txn.status,
                "payoutStatus": txn.payout_status,
                "transferCode": txn.transfer_code,
                "accountName": txn.account_name,
                "createdAt": txn.created_at.isoformat() if txn.created_at else None,
            },
        }

    try:
        resp = await verify_transfer(reference)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Paystack verify_transfer failed: {str(e)[:300]}")

    ps = (resp.get("data", {}) or {}).get("status")
    user = db.query(User).filter(User.id == current_user.id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc)

    if ps == "success":
        txn.status = "COMPLETED"
        txn.payout_status = "success"
        txn.payout_completed_at = now
        db.commit()
    elif ps in ("failed", "reversed"):
        user.balance = (user.balance or Decimal("0.00")) + txn.amount
        txn.status = "REVERSED" if ps == "reversed" else "FAILED"
        txn.payout_status = ps
        txn.payout_completed_at = now
        db.commit()
    else:
        txn.status = "PROCESSING"
        txn.payout_status = ps or "pending"
        db.commit()

    return {
        "success": True,
        "data": {
            "transactionId": str(txn.id),
            "amount": txn.amount,
            "newBalance": user.balance,
            "type": txn.type,
            "reference": txn.reference,
            "status": txn.status,
            "payoutStatus": txn.payout_status,
            "transferCode": txn.transfer_code,
            "accountName": txn.account_name,
            "createdAt": txn.created_at.isoformat() if txn.created_at else None,
        },
    }


@router.get("/history", response_model=TransactionHistoryResponse)
def transaction_history(
    limit: int = Query(20, ge=1),
    offset: int = Query(0, ge=0),
    type: str = Query("ALL"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)

    if type != "ALL":
        query = query.filter(Transaction.type == type)

    total = query.count()

    txns = (
        query.order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "success": True,
        "data": [
            {
                "id": str(t.id),
                "amount": t.amount,
                "type": t.type,
                "reference": t.reference,
                "status": t.status,
                "createdAt": t.created_at,
            }
            for t in txns
        ],
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }
