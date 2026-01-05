from fastapi import APIRouter, HTTPException, Request, Header, Depends
from sqlalchemy.orm import Session

from payment_service.app.schemas.payment import PaystackPayment
from payment_service.app.services.paystack_service import (
    initialize_payment,
    verify_webhook_signature,
)
from payment_service.app.models.payment import Payment
from payment_service.app.db.session import get_db

router = APIRouter(prefix="/paystack", tags=["Paystack"])


@router.post("/initialize")
async def paystack_initialize(
    data: PaystackPayment,
    db: Session = Depends(get_db),
):
    response = await initialize_payment(data.email, data.amount)

    reference = response["data"]["reference"]

    existing = db.query(Payment).filter_by(reference=reference).first()
    if existing:
        return response  # idempotent safe return

    payment = Payment(
        reference=reference,
        email=data.email,
        amount=data.amount,
        currency="NGN",
        status="pending",
    )

    db.add(payment)
    db.commit()

    return response


@router.get("/verify/{reference}")
async def verify_payment_status(
    reference: str,
    db: Session = Depends(get_db),
):
    payment = db.query(Payment).filter_by(reference=reference).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Not found")

    return {
        "reference": payment.reference,
        "status": payment.status,
        "amount": payment.amount,
        "currency": payment.currency,
        "verified": payment.verified,
    }


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
    event = payload.get("event")

    if event != "charge.success":
        return {"status": "ignored"}

    data = payload["data"]

    reference = data["reference"]
    amount = data["amount"] / 100
    currency = data["currency"]

    payment = (
        db.query(Payment)
        .filter_by(reference=reference)
        .with_for_update()
        .first()
    )

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")


    if payment.verified:
        return {"status": "already processed"}


    if currency != "NGN":
        raise HTTPException(status_code=400, detail="Invalid currency")

    if float(payment.amount) != float(amount):
        raise HTTPException(status_code=400, detail="Amount mismatch")

    payment.status = "success"
    payment.verified = True

    db.commit()

    return {"status": "payment verified"}
