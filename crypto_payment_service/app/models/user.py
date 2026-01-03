from sqlalchemy import Column, Integer, String, Numeric
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    balance = Column(Numeric(18, 6), default=0)
