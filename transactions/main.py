from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from decimal import Decimal

from core.database import get_db
from core.models import User, Transaction
from transactions.schemas import (
    DepositRequest,
    WithdrawRequest,
    TransactionResponse,
    TransactionHistoryResponse,
)
from core.auth import get_current_user

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


@router.post("/deposit", response_model=TransactionResponse)
def deposit_funds(
    payload: DepositRequest,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    # Prevent duplicate references
    if payload.reference:
        existing = db.query(Transaction).filter_by(reference=payload.reference).first()
        if existing:
            raise HTTPException(status_code=400, detail="Duplicate transaction reference")

    user = db.query(User).filter(User.id == current_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update balance
    user.balance = (user.balance or Decimal("0.00")) + payload.amount

    txn = Transaction(
        user_id=current_user,
        amount=payload.amount,
        type="DEPOSIT",
        reference=payload.reference,
        status="COMPLETED",
    )

    db.add(txn)
    db.commit()
    db.refresh(txn)

    return {
        "success": True,
        "data": {
            "transactionId": str(txn.id),
            "amount": payload.amount,
            "newBalance": user.balance,
            "status": txn.status,
            "createdAt": txn.created_at.isoformat(),
        },
    }


@router.post("/withdraw", response_model=TransactionResponse)
def withdraw_funds(
    payload: WithdrawRequest,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    user = db.query(User).filter(User.id == current_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.balance is None or user.balance < payload.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    # Deduct balance
    user.balance -= payload.amount

    txn = Transaction(
        user_id=current_user,
        amount=payload.amount,
        type="WITHDRAWAL",
        status="PENDING",
    )

    db.add(txn)
    db.commit()
    db.refresh(txn)

    return {
        "success": True,
        "data": {
            "transactionId": str(txn.id),
            "amount": payload.amount,
            "newBalance": user.balance,
            "status": txn.status,
            "createdAt": txn.created_at.isoformat(),
        },
    }


@router.get("/history", response_model=TransactionHistoryResponse)
def transaction_history(
    limit: int = Query(20, ge=1),
    offset: int = Query(0, ge=0),
    type: str = Query("ALL"),
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    query = db.query(Transaction).filter(Transaction.user_id == current_user)

    if type != "ALL":
        query = query.filter(Transaction.type == type)

    total = query.count()
    txns = (
        query.order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "success": True,
        "data": [
            {
                "id": str(t.id),
                "amount": t.amount,
                "type": t.type,
                "reference": t.reference,
                "status": t.status,
                "createdAt": t.created_at.isoformat(),
            }
            for t in txns
        ],
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }
