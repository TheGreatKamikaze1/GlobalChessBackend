from fastapi import APIRouter, HTTPException
from app.services.tron_service import send_usdt

router = APIRouter(prefix="/withdraw", tags=["Withdraw"])

@router.post("/")
def withdraw(address: str, amount: float):
    try:
        tx_hash = send_usdt(address, amount)
        return {"tx_hash": tx_hash}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
