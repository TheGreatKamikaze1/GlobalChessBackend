from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base



# USER

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    password = Column(String, nullable=False)

    balance = Column(Numeric(12, 2), default=0.00)
    avatar_url = Column(String, nullable=True)

    games_played = Column(Integer, default=0)
    games_won = Column(Integer, default=0)
    current_rating = Column(Integer, default=1200)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
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


# CHALLENGE

class Challenge(Base):
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True, index=True)

    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    acceptor_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    stake = Column(Numeric(12, 2), nullable=False)
    time_control = Column(String, default="60/0")

    status = Column(String, default="OPEN")  # OPEN | ACCEPTED | CANCELLED
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    creator = relationship(
        "User",
        back_populates="created_challenges",
        foreign_keys=[creator_id],
    )

    acceptor = relationship(
        "User",
        back_populates="accepted_challenges",
        foreign_keys=[acceptor_id],
    )

    game = relationship(
        "Game",
        back_populates="challenge",
        uselist=False,
    )


# GAME

class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)

    challenge_id = Column(
        Integer,
        ForeignKey("challenges.id"),
        unique=True,
        nullable=True,
    )

    white_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    black_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    stake = Column(Numeric(12, 2), nullable=False)

    status = Column(String, default="ONGOING")  # ONGOING | COMPLETED
    result = Column(String, nullable=True)      # WHITE_WIN | BLACK_WIN | DRAW
    winner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    moves = Column(Text, default="[]", nullable=False)
    current_fen = Column(
        String,
        default="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        nullable=False,
    )

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    white = relationship(
        "User",
        foreign_keys=[white_id],
        back_populates="games_as_white",
    )

    black = relationship(
        "User",
        foreign_keys=[black_id],
        back_populates="games_as_black",
    )

    challenge = relationship(
        "Challenge",
        back_populates="game",
    )


# TRANSACTIONS

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)

    type = Column(String, nullable=False)
    # DEPOSIT | WITHDRAWAL | WIN | LOSS

    reference = Column(String, unique=True, nullable=True)
    status = Column(String, default="PENDING")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
