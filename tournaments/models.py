from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Numeric,
    Boolean,
    ForeignKey,
    JSON,
)
from sqlalchemy.sql import func
import uuid

from core.database import Base


class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    creator_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    entry_fee = Column(Numeric(10, 2), default=0)
    deposit_required = Column(Boolean, default=True)

    prize_rules = Column(JSON, nullable=False)
    # example:
    # {
    #   "places": [1,2,3],
    #   "distribution": [0.5, 0.3, 0.2]
    # }

    time_control = Column(String, nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, nullable=False)

    status = Column(String, default="UPCOMING") 
    escrow_balance = Column(Numeric(10, 2), default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TournamentParticipant(Base):
    __tablename__ = "tournament_participants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tournament_id = Column(String(36), ForeignKey("tournaments.id"))
    user_id = Column(String(36), ForeignKey("users.id"))

    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    score = Column(Integer, default=0)
    paid = Column(Boolean, default=False)  # Did the participant deposit to join?
