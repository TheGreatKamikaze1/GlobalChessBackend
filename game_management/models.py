from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from db import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    password = Column(String, nullable=False)
    balance = Column(Integer, default=0)


# relationships
    white_games = relationship("Game", foreign_keys="Game.white_id", back_populates="white")
    black_games = relationship("Game", foreign_keys="Game.black_id", back_populates="black")


class Game(Base):
    __tablename__ = "games"


    id = Column(Integer, primary_key=True, index=True)


    white_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    black_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    white = relationship("User", foreign_keys=[white_id], back_populates="white_games")
    black = relationship("User", foreign_keys=[black_id], back_populates="black_games")


    stake = Column(Integer, default=0, nullable=False)
    status = Column(String, default="ONGOING", nullable=False)
    result = Column(String, nullable=True) # WHITE_WIN, BLACK_WIN, DRAW
    winner_id = Column(Integer, ForeignKey("users.id"), nullable=True)


    moves = Column(String, default="[]", nullable=False) # JSON string
    current_fen = Column(String, default="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", nullable=False)


    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)