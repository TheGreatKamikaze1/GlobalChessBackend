from fastapi import APIRouter
from app.schemas.deposit import DepositRequest

router = APIRouter(prefix="/deposit", tags=["Deposit"])

@router.post("/address")
def generate_address():
    # Normally you'd generate per-user wallet
    return {
        "network": "TRON",
        "address": "YOUR_FIXED_DEPOSIT_ADDRESS"
    }
