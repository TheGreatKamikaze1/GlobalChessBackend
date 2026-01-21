from fastapi import APIRouter, HTTPException, Request, Header, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from decimal import Decimal
import httpx

from payment_service.app.schemas.payment import PaystackPayment
from payment_service.app.services.paystack_service import (
    initialize_payment,
    verify_webhook_signature,
    verify_payment,
)
from payment_service.app.models.payment import Payment
from payment_service.app.db.session import get_db
from payment_service.app.core.config import settings

router = APIRouter(prefix="/paystack", tags=["Paystack"])


def _transaction_url() -> str:
    if not settings.CORE_API_BASE_URL:
        raise HTTPException(
            status_code=500,
            detail="CORE_API_BASE_URL is not set (needed to credit wallet).",
        )
    return f"{str(settings.CORE_API_BASE_URL).rstrip('/')}/api/transactions/deposit"


async def _credit_wallet(amount: Decimal, reference: str, access_token: str):
    url = _transaction_url()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url,
            json={
                "amount": str(amount),       # Decimal-safe
                "reference": reference,
            },
            headers={
                "x-internal-call": "PAYSTACK",
                "Authorization": f"Bearer {access_token}",
            },
            follow_redirects=True,
        )

    if resp.status_code < 200 or resp.status_code >= 300:
        detail = (resp.text or "")[:300]
        raise HTTPException(status_code=502, detail=f"Deposit failed {resp.status_code}: {detail}")


@router.post("/initialize")
async def paystack_initialize(
    data: PaystackPayment,
    db: Session = Depends(get_db),
):
    response = await initialize_payment(data.email, data.amount)
    reference = response["data"]["reference"]

    existing = db.query(Payment).filter_by(reference=reference).first()
    if existing:
        return response

    payment = Payment(
        reference=reference,
        email=data.email,
        amount=data.amount,  # stored in NAIRA
        currency="NGN",
        status="pending",
        provider="paystack",
        access_token=data.access_token,
    )

    try:
        db.add(payment)
        db.commit()
    except IntegrityError:
        db.rollback()
        return response

    return response


@router.post("/webhook")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str = Header(None),
    db: Session = Depends(get_db),
):
    body = await request.body()
    if not verify_webhook_signature(body, x_paystack_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    if payload.get("event") != "charge.success":
        return {"status": "ignored"}

    data = payload.get("data") or {}
    reference = data.get("reference")
    if not reference:
        raise HTTPException(status_code=400, detail="Missing reference")

    # Paystack amount is in kobo (int)
    amount = (Decimal(str(data.get("amount", 0))) / Decimal("100"))

    payment = (
        db.query(Payment)
        .filter_by(reference=reference)
        .with_for_update()
        .first()
    )

    if not payment:
        return {"status": "not tracked"}

    if payment.verified:
        return {"status": "already processed"}

    # Credit wallet FIRST (idempotent deposit prevents double-credit)
    await _credit_wallet(amount=amount, reference=reference, access_token=payment.access_token)

    # Then mark payment verified
    payment.status = "success"
    payment.verified = True
    payment.amount = amount
    db.commit()

    return {"status": "payment verified and wallet credited"}


@router.get("/verify/{reference}")
async def verify_paystack_payment(
    reference: str,
    db: Session = Depends(get_db),
):
    response = await verify_payment(reference)
    if response.get("data", {}).get("status") != "success":
        raise HTTPException(status_code=400, detail="Payment not successful")

    payment = db.query(Payment).filter_by(reference=reference).with_for_update().first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    if payment.verified:
        return {"status": "already verified", "reference": reference}

    amount = (Decimal(str(response["data"]["amount"])) / Decimal("100"))

    await _credit_wallet(amount=amount, reference=reference, access_token=payment.access_token)

    payment.status = "success"
    payment.verified = True
    payment.amount = amount
    db.commit()

    return {
        "status": "verified",
        "reference": reference,
        "amount": float(payment.amount),
        "currency": payment.currency,
    }
