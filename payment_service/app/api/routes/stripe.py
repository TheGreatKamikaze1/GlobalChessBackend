from fastapi import APIRouter, HTTPException
from app.schemas.payment import StripePayment
from app.services.stripe_service import create_payment_intent

router = APIRouter(prefix="/stripe", tags=["Stripe"])

@router.post("/pay")
def stripe_pay(data: StripePayment):
    try:
        intent = create_payment_intent(data.amount, data.currency)
        return {"client_secret": intent["client_secret"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
