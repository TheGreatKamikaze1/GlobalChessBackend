from sqlalchemy import Column, Integer, String, Numeric
from app.core.database import Base

class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    address = Column(String)
    amount = Column(Numeric(18, 6))
    status = Column(String)  # pending / completed
