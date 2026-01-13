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

    max_players = Column(Integer, nullable=False, default=64)
    format = Column(String, nullable=False, default="Swiss")
    rounds = Column(Integer, nullable=False, default=7)

    time_control = Column(String, nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, nullable=False)

    status = Column(String, default="UPCOMING")
    escrow_balance = Column(Numeric(10, 2), default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TournamentParticipant(Base):
    __tablename__ = "tournament_participants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tournament_id = Column(String(36), ForeignKey("tournaments.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    score = Column(Numeric(4, 1), default=0.0)
    paid = Column(Boolean, default=False)


class TournamentMatch(Base):
    __tablename__ = "tournament_matches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tournament_id = Column(String(36), ForeignKey("tournaments.id"), nullable=False)

    round = Column(Integer, nullable=False)
    white_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    black_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    status = Column(String, default="scheduled")  # scheduled, live, completed
    result = Column(String, nullable=True)  # "1-0", "0-1", "1/2-1/2"

    created_at = Column(DateTime(timezone=True), server_default=func.now())
