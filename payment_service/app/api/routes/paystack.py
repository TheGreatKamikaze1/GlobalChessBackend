from fastapi import APIRouter, HTTPException, Request, Header, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
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


def _norm_email(email: str) -> str:
    return email.strip().lower()


def _transaction_deposit_url(request: Request | None = None) -> str:
   
    base = str(settings.CORE_API_BASE_URL).rstrip("/") if settings.CORE_API_BASE_URL else None
    if not base:
        if not request:
           
            base = "http://localhost:8000"
        else:
            base = str(request.base_url).rstrip("/")

    return f"{base}/api/transactions/deposit"


async def _credit_wallet(amount: float, reference: str, access_token: str, request: Request | None = None):
    url = _transaction_deposit_url(request)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url,
            json={"amount": amount, "reference": reference},
            headers={
                "x-internal-call": "PAYSTACK",
                "Authorization": f"Bearer {access_token}",
            },
        )

    if resp.status_code < 200 or resp.status_code >= 300:
        raise HTTPException(
            status_code=502,
            detail=f"Wallet credit failed (transactions service): {resp.status_code}",
        )


@router.post("/initialize")
async def paystack_initialize(
    data: PaystackPayment,
    db: Session = Depends(get_db),
):
    email = _norm_email(data.email)

    response = await initialize_payment(email, data.amount)
    reference = response["data"]["reference"]

    existing = db.query(Payment).filter_by(reference=reference).first()
    if existing:
        return response

    payment = Payment(
        reference=reference,
        email=email,
        amount=data.amount,         
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

    # Only process successful charges
    if payload.get("event") != "charge.success":
        return {"status": "ignored"}

    data = payload.get("data") or {}
    reference = data.get("reference")
    if not reference:
        raise HTTPException(status_code=400, detail="Missing reference")

    # Paystack gives amount in kobo
    amount = float(data.get("amount", 0)) / 100.0

    payment = (
        db.query(Payment)
        .filter_by(reference=reference)
        .with_for_update()
        .first()
    )

   
    if not payment:
        return {"status": "payment not tracked"}

    if payment.verified:
        return {"status": "already processed"}

    if not payment.access_token:
        raise HTTPException(status_code=400, detail="Missing payment access token")


    try:
        if float(payment.amount) != float(amount):
            payment.amount = amount
    except Exception:
        # keep going even if decimal conversion is weird
        payment.amount = amount

    # Credit wallet FIRST, then mark verified
    await _credit_wallet(amount=amount, reference=reference, access_token=payment.access_token, request=request)

    payment.status = "success"
    payment.verified = True
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

    # Paystack returns amount in kobo
    paystack_amount = float(response["data"]["amount"]) / 100.0

    if not payment.access_token:
        raise HTTPException(status_code=400, detail="Missing payment access token")

    # Credit wallet
    await _credit_wallet(amount=paystack_amount, reference=reference, access_token=payment.access_token)

    payment.status = "success"
    payment.verified = True
    payment.amount = paystack_amount
    db.commit()

    return {
        "status": "verified",
        "reference": reference,
        "amount": float(payment.amount),
        "currency": payment.currency,
    }
