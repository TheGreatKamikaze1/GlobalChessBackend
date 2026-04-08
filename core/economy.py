from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.models import Transaction, User

MONEY_QUANTUM = Decimal("0.01")


def to_money(value: Decimal | float | int | str | None) -> Decimal:
    if isinstance(value, Decimal):
        amount = value
    else:
        amount = Decimal(str(value or 0))
    return amount.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def money_to_float(value: Decimal | float | int | str | None) -> float:
    return float(to_money(value))


def user_balance(user: User | None) -> Decimal:
    if not user:
        return Decimal("0.00")
    return to_money(getattr(user, "balance", Decimal("0.00")) or Decimal("0.00"))


def ensure_sufficient_balance(
    user: User,
    amount: Decimal | float | int | str,
    *,
    detail: str = "Insufficient wallet balance",
) -> Decimal:
    normalized = to_money(amount)
    if user_balance(user) < normalized:
        raise HTTPException(status_code=400, detail=detail)
    return normalized


def debit_user_balance(user: User, amount: Decimal | float | int | str) -> Decimal:
    normalized = ensure_sufficient_balance(user, amount)
    user.balance = user_balance(user) - normalized
    return normalized


def credit_user_balance(user: User, amount: Decimal | float | int | str) -> Decimal:
    normalized = to_money(amount)
    user.balance = user_balance(user) + normalized
    return normalized


def create_transaction_record(
    db: Session,
    *,
    user_id: str,
    amount: Decimal | float | int | str,
    type: str,
    reference: str | None,
    status: str = "COMPLETED",
    provider: str = "internal",
    payout_status: str | None = None,
    meta: dict[str, Any] | None = None,
) -> Transaction:
    txn = Transaction(
        user_id=user_id,
        amount=to_money(amount),
        type=type,
        reference=reference,
        status=status,
        provider=provider,
        payout_status=payout_status,
        meta=meta,
    )
    db.add(txn)
    return txn
