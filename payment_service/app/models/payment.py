from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from payment_service.app.db.base import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)

    reference = Column(String, nullable=False, unique=True, index=True)
    email = Column(String, nullable=False)

    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default="NGN")

    status = Column(String, nullable=False)  # pending | success | failed
    provider = Column(String, default="paystack")

    verified = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("reference", name="uq_payment_reference"),
    )
