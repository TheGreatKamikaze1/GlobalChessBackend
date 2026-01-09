from fastapi import APIRouter, HTTPException, Request, Header, Depends
from sqlalchemy.orm import Session
import httpx

from payment_service.app.schemas.payment import PaystackPayment
from payment_service.app.services.paystack_service import (
    initialize_payment,
    verify_webhook_signature,
)
from payment_service.app.models.payment import Payment
from payment_service.app.db.session import get_db
from payment_service.app.services.paystack_service import verify_payment

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
        return response

    payment = Payment(
        reference=reference,
        email=data.email,
          amount=data.amount,
        currency="NGN",
        status="pending",
        provider="paystack",
        access_token=data.access_token,
    )
    

    db.add(payment)
    db.commit()
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

    data = payload["data"]
    reference = data["reference"]
    amount = data["amount"] / 100

    payment = (
        db.query(Payment)
        .filter_by(reference=reference)
        .with_for_update()
        .first()
    )

    if not payment or payment.verified:
        return {"status": "already processed or not found"}

    payment.status = "success"
    payment.verified = True
    db.commit()

    TRANSACTION_URL = (
        "https://globalchessbackend-production.up.railway.app"
        "/api/transactions/deposit"
    )

    async with httpx.AsyncClient() as client:
        await client.post(
            TRANSACTION_URL,
            json={
                "amount": amount,
                "reference": reference,
            },
            headers={
                "x-internal-call": "PAYSTACK",
            
                "Authorization": f"Bearer {payment.access_token}",
            },
            timeout=10,
        )

    return {"status": "payment verified and wallet credited"}


@router.get("/verify/{reference}")
async def verify_paystack_payment(
    reference: str,
    db: Session = Depends(get_db),
):
   
    response = await verify_payment(reference)

    if response["data"]["status"] != "success":
        raise HTTPException(
            status_code=400,
            detail="Payment not successful"
        )

    payment = (
        db.query(Payment)
        .filter_by(reference=reference)
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment record not found"
        )

    
    if payment.verified:
        return {
            "status": "already verified",
            "reference": reference,
        }

   
    payment.status = "success"
    payment.verified = True
    db.commit()

    return {
        "status": "verified",
        "reference": reference,
        "amount": float(payment.amount),
        "currency": payment.currency,
    }

