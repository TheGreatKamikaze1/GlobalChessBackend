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

router = APIRouter(prefix="/paystack", tags=["Payments"])

TRANSFER_EVENT_TO_STATUS = {
    "transfer.success": "success",
    "transfer.failed": "failed",
    "transfer.reversed": "reversed",
}


def _transaction_url() -> str:
    return f"{str(settings.CORE_API_BASE_URL).rstrip('/')}/api/transactions/deposit"


def _withdraw_webhook_url() -> str:
    return f"{str(settings.CORE_API_BASE_URL).rstrip('/')}/api/transactions/withdraw/webhook"


async def _credit_wallet(amount: Decimal, reference: str, access_token: str):
    url = _transaction_url()
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.post(
                url,
                json={
                    "amount": str(amount),
                    "reference": reference,
                },
                headers={
                    "x-internal-call": "PAYSTACK",
                    "Authorization": f"Bearer {access_token}",
                },
            )
    except httpx.RequestError as e:
        # Force Paystack retry by returning 502
        raise HTTPException(status_code=502, detail=f"Deposit call network error: {str(e)[:200]}")

    if resp.status_code < 200 or resp.status_code >= 300:
        detail = (resp.text or "")[:500]
        raise HTTPException(status_code=502, detail=f"Deposit failed {resp.status_code}: {detail}")


async def _notify_withdrawal_status(reference: str, status: str, transfer_code: str | None, event: str):
    if not settings.INTERNAL_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="INTERNAL_WEBHOOK_SECRET is not set")

    url = _withdraw_webhook_url()

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.post(
                url,
                json={
                    "reference": reference,
                    "status": status,  # success | failed | reversed
                    "transfer_code": transfer_code,
                    "event": event,
                },
                headers={
                    "x-internal-call": "PAYSTACK",
                    "x-internal-secret": settings.INTERNAL_WEBHOOK_SECRET,
                },
            )
    except httpx.RequestError as e:
     
        raise HTTPException(status_code=502, detail=f"Withdraw update network error: {str(e)[:200]}")

    if resp.status_code < 200 or resp.status_code >= 300:
        detail = (resp.text or "")[:500]
        
        raise HTTPException(status_code=502, detail=f"Withdrawal update failed {resp.status_code}: {detail}")


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
        amount=Decimal(str(data.amount)),  # stored in NAIRA
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
    x_paystack_signature: str = Header(None, alias="x-paystack-signature"),
    db: Session = Depends(get_db),
):
    body = await request.body()
    if not verify_webhook_signature(body, x_paystack_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = payload.get("event")
    data = payload.get("data") or {}

   
    if event in TRANSFER_EVENT_TO_STATUS:
        reference = data.get("reference")
        transfer_code = data.get("transfer_code")

        if not reference:
         
            return {"status": "ignored", "reason": "missing transfer reference"}

        await _notify_withdrawal_status(
            reference=reference,
            status=TRANSFER_EVENT_TO_STATUS[event],
            transfer_code=transfer_code,
            event=event,
        )
        return {"status": "processed", "event": event, "reference": reference}

  
    if event != "charge.success":
        return {"status": "ignored"}

    reference = data.get("reference")
    if not reference:
        raise HTTPException(status_code=400, detail="Missing reference")

    # Paystack amount is in kobo
    amount = (Decimal(str(data.get("amount", 0))) / Decimal("100"))

    payment = (
        db.query(Payment)
        .filter_by(reference=reference)
        .with_for_update()
        .first()
    )

    if not payment:
    # If you want, you can still return 200 to avoid retries
        return {"status": "not tracked"}

    if payment.verified:
        return {"status": "already processed"}

    await _credit_wallet(amount=amount, reference=reference, access_token=payment.access_token)

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

    payment = (
        db.query(Payment)
        .filter_by(reference=reference)
        .with_for_update()
        .first()
    )
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
