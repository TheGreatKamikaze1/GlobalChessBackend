from fastapi import APIRouter, HTTPException
from app.schemas.payment import PaystackPayment
from app.services.paystack_service import initialize_payment

router = APIRouter(prefix="/paystack", tags=["Paystack"])

@router.post("/pay")
async def paystack_pay(data: PaystackPayment):
    try:
        return await initialize_payment(data.email, data.amount)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
