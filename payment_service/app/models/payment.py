from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.sql import func
import uuid

from payment_service.app.db.base import Base




class Payment(Base):
    __tablename__ = "payments"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))

    reference = Column(String, nullable=False, unique=True, index=True)
    email = Column(String, nullable=False)

    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default="NGN")
    


    status = Column(String, nullable=False)  # pending | success | failed
    provider = Column(String, default="paystack")

    verified = Column(Boolean, default=False)
    access_token = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("reference", name="uq_payment_reference"),
    )