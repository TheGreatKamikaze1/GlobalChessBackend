from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
import uuid

app = FastAPI()

# --- Mock Database / Models ---
# In a real app, these would be SQLAlchemy or Tortoise models
mock_db = {
    "users": {
        "user_123": {"balance": 1500.00}
    },
    "transactions": []
}

# --- Request/Response Schemas ---

class DepositRequest(BaseModel):
    amount: float = Field(gt=0)
    paymentMethod: str
    reference: str

class AccountDetails(BaseModel):
    bankName: str
    accountNumber: str

class WithdrawRequest(BaseModel):
    amount: float = Field(gt=0)
    accountDetails: AccountDetails

class TransactionResponseData(BaseModel):
    transactionId: str
    amount: float
    newBalance: float
    status: str
    createdAt: datetime

class TransactionResponse(BaseModel):
    success: bool
    data: TransactionResponseData

# --- API Endpoints ---

@app.post("/api/transactions/deposit", response_model=TransactionResponse)
async def deposit_funds(request: DepositRequest):
    # 1. Identify User (Logic would usually pull from a JWT token)
    user_id = "user_123" 
    
    # 2. Update Balance
    mock_db["users"][user_id]["balance"] += request.amount
    new_balance = mock_db["users"][user_id]["balance"]
    
    # 3. Create Transaction Record
    transaction_id = str(uuid.uuid4())
    txn_record = {
        "id": transaction_id,
        "user_id": user_id,
        "amount": request.amount,
        "type": "DEPOSIT",
        "reference": request.reference,
        "status": "COMPLETED",
        "createdAt": datetime.utcnow()
    }
    mock_db["transactions"].append(txn_record)

    return {
        "success": True,
        "data": {
            "transactionId": transaction_id,
            "amount": request.amount,
            "newBalance": new_balance,
            "status": "COMPLETED",
            "createdAt": txn_record["createdAt"]
        }
    }

@app.post("/api/transactions/withdraw", response_model=TransactionResponse)
async def withdraw_funds(request: WithdrawRequest):
    user_id = "user_123"
    current_balance = mock_db["users"][user_id]["balance"]

    # 1. Check Sufficiency
    if current_balance < request.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    # 2. Update Balance
    mock_db["users"][user_id]["balance"] -= request.amount
    new_balance = mock_db["users"][user_id]["balance"]

    # 3. Create Transaction Record
    transaction_id = str(uuid.uuid4())
    txn_record = {
        "id": transaction_id,
        "user_id": user_id,
        "amount": request.amount,
        "type": "WITHDRAWAL",
        "status": "PENDING",
        "createdAt": datetime.utcnow()
    }
    mock_db["transactions"].append(txn_record)

    return {
        "success": True,
        "data": {
            "transactionId": transaction_id,
            "amount": request.amount,
            "newBalance": new_balance,
            "status": "PENDING",
            "createdAt": txn_record["createdAt"]
        }
    }

@app.get("/api/transactions/history")
async def get_history(
    limit: int = 20,
    offset: int = 0,
    type: str = Query("ALL", regex="^(ALL|DEPOSIT|WITHDRAWAL|WIN|LOSS)$")
):
    user_id = "user_123"
    
    # 1. Filter transactions
    user_txns = [t for t in mock_db["transactions"] if t["user_id"] == user_id]
    
    if type != "ALL":
        user_txns = [t for t in user_txns if t["type"] == type]

    # 2. Paginate
    paginated_txns = user_txns[offset : offset + limit]

    return {
        "success": True,
        "data": paginated_txns,
        "pagination": {
            "total": len(user_txns),
            "limit": limit,
            "offset": offset
        }
    }
    
    
    