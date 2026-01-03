from sqlalchemy import Column, Integer, String, Numeric
from app.core.database import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    tx_hash = Column(String)
    amount = Column(Numeric(18, 6))
    status = Column(String)  # pending / confirmed
