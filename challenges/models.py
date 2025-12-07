from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
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
    balance = Column(Float, default=0) 

    # relationships
    created_challenges = relationship("Challenge", back_populates="creator", foreign_keys="[Challenge.creator_id]")
    accepted_challenges = relationship("Challenge", back_populates="acceptor", foreign_keys="[Challenge.acceptor_id]")
    
   
    games_as_white = relationship("Game", back_populates="white_player", foreign_keys="[Game.white_id]")
    games_as_black = relationship("Game", back_populates="black_player", foreign_keys="[Game.black_id]")


class Challenge(Base):
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    acceptor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    stake = Column(Float, nullable=False)
    time_control = Column(String, default="60/0")
    
    status = Column(String, default="OPEN") 
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    # relationships
    creator = relationship("User", back_populates="created_challenges", foreign_keys="[Challenge.creator_id]")
    acceptor = relationship("User", back_populates="accepted_challenges", foreign_keys="[Challenge.acceptor_id]")
    game = relationship("Game", back_populates="challenge", uselist=False) # One-to-one with Game


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), unique=True, nullable=False)
    white_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    black_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stake = Column(Float, nullable=False)
    
    # Relationships
    challenge = relationship("Challenge", back_populates="game")
    white_player = relationship("User", foreign_keys="[Game.white_id]", back_populates="games_as_white")
    black_player = relationship("User", foreign_keys="[Game.black_id]", back_populates="games_as_black")