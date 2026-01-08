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
from payment_service.app.core.config import settings


router = APIRouter( tags=["Paystack"])


@router.post("/webhook")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str = Header(None),
    db: Session = Depends(get_db),
):
    body = await request.body()

    if not verify_webhook_signature(body, x_paystack_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    event = await request.json()

    if event.get("event") != "charge.success":
        return {"status": "ignored"}

    data = event["data"]

    reference = data["reference"]
    amount = data["amount"] / 100  
    currency = data["currency"]

    if currency != "NGN":
        raise HTTPException(status_code=400, detail="Invalid currency")


    payment = (
        db.query(Payment)
        .filter(Payment.reference == reference)
        .with_for_update()
        .first()
    )

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.verified:
        return {"status": "already processed"}

   
    if float(payment.amount) != float(amount):
        raise HTTPException(status_code=400, detail="Amount mismatch")

   
    payment.status = "success"
    payment.verified = True
    db.commit()

    # CREDIT USER WALLET
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.TRANSACTIONS_BASE_URL}/transactions/deposit",
            headers={
                "Authorization": f"Bearer {payment.user_token}",
                "X-Internal-Call": "PAYSTACK",
            },
            json={
                "amount": amount,
                "reference": reference,
            },
            timeout=10,
        )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail="Failed to credit user wallet",
            )

    return {"status": "payment verified & wallet credited"}
