from datetime import datetime
import uuid
from decimal import Decimal
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Text, Integer, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

from core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))

    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    password = Column(String, nullable=False)

    name = Column(String(100), nullable=True)
    bio = Column(Text, nullable=True)

    balance = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    avatar_url = Column(String, nullable=True)
    games_played = Column(Integer, default=0, nullable=False)
    games_won = Column(Integer, default=0, nullable=False)
    current_rating = Column(Integer, default=1200, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    created_challenges = relationship(
        "Challenge",
        back_populates="creator",
        foreign_keys="Challenge.creator_id",
    )

    accepted_challenges = relationship(
        "Challenge",
        back_populates="acceptor",
        foreign_keys="Challenge.acceptor_id",
    )

    games_as_white = relationship(
        "Game",
        back_populates="white",
        foreign_keys="Game.white_id",
    )

    games_as_black = relationship(
        "Game",
        back_populates="black",
        foreign_keys="Game.black_id",
    )

    transactions = relationship("Transaction", back_populates="user")


class Challenge(Base):
    __tablename__ = "challenges"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))

    creator_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    acceptor_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)

    stake = Column(Numeric(12, 2), nullable=False)
    time_control = Column(String, default="60/0")

    status = Column(String, default="OPEN", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    color_preference = Column(String, default="auto")

    creator = relationship("User", back_populates="created_challenges", foreign_keys=[creator_id])
    acceptor = relationship("User", back_populates="accepted_challenges", foreign_keys=[acceptor_id])

    game = relationship("Game", back_populates="challenge", uselist=False)

    __table_args__ = (
        Index("ix_challenges_open_unexpired", "status", "expires_at"),
    )


class Game(Base):
    __tablename__ = "games"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))

    challenge_id = Column(String(36), ForeignKey("challenges.id"), unique=True, nullable=True, index=True)

    white_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    black_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    stake = Column(Numeric(12, 2), nullable=False)

    status = Column(String, default="ONGOING", index=True)
    result = Column(String, nullable=True)
    winner_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)

    moves = Column(Text, default="[]", nullable=False)
    current_fen = Column(
        String,
        default="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        nullable=False,
    )

    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    white = relationship("User", foreign_keys=[white_id], back_populates="games_as_white")
    black = relationship("User", foreign_keys=[black_id], back_populates="games_as_black")

    challenge = relationship("Challenge", back_populates="game")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))

    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)

    type = Column(String, nullable=False, index=True)
    reference = Column(String, unique=True, nullable=True)

    # PENDING | PROCESSING | OTP_REQUIRED | COMPLETED | FAILED | REVERSED
    status = Column(String, default="PENDING", index=True)

    # --- Payout / Withdrawal audit fields ---
    provider = Column(String(32), nullable=True)             
    payout_status = Column(String(32), nullable=True)       

    bank_code = Column(String(10), nullable=True)            
    bank_name = Column(String(120), nullable=True)          
    account_name = Column(Text, nullable=True)               
    account_number_last4 = Column(String(4), nullable=True) 

    recipient_code = Column(String(64), nullable=True)       
    transfer_code = Column(String(64), nullable=True)        

    withdrawal_reason = Column(Text, nullable=True)

    payout_initiated_at = Column(DateTime(timezone=True), nullable=True)
    payout_completed_at = Column(DateTime(timezone=True), nullable=True)

    payout_event = Column(String(64), nullable=True)         # e.g. transfer.success

    meta = Column(JSONB, nullable=True)                      

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="transactions")

    __table_args__ = (
        
        Index("ix_transactions_withdrawals_reference", "reference", postgresql_where=(type == "WITHDRAWAL")),
        Index("ix_transactions_withdrawals_status_created", "status", "created_at", postgresql_where=(type == "WITHDRAWAL")),
    )

