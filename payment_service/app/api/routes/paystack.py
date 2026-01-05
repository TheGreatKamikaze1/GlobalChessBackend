from fastapi import APIRouter, HTTPException, Request, Header
from payment_service.app.schemas.payment import PaystackPayment
from payment_service.app.services.paystack_service import (
    initialize_payment,
    verify_payment,
    verify_webhook_signature,
)

router = APIRouter( tags=["Paystack"])


@router.post("/initialize")
async def paystack_initialize(data: PaystackPayment):
    """
    Initialize a Paystack transaction
    """
    try:
        return await initialize_payment(data.email, data.amount)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/verify/{reference}")
async def paystack_verify(reference: str):
    """
    Verify transaction after payment
    """
    try:
        return await verify_payment(reference)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str = Header(None),
):
    """
    Paystack webhook endpoint
    """
    body = await request.body()

    if not verify_webhook_signature(body, x_paystack_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()

    event = payload.get("event")

    if event == "charge.success":
        data = payload["data"]
       
        return {"status": "payment successful"}

    return {"status": "ignored"}
