from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from db import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    displayName = Column(String, nullable=False)
    password = Column(String, nullable=False)
    balance = Column(Numeric(12, 2), default=0.00)
    currentRating = Column(Integer, default=1200)
    avatarUrl = Column(String, nullable=True)

class Game(Base):
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, index=True)
    white_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    black_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stake = Column(Numeric(12, 2), nullable=False)
    status = Column(String, default="ONGOING") # ONGOING, COMPLETED
    result = Column(String, nullable=True) # WHITE_WIN, BLACK_WIN, DRAW
    
    # Store moves as a JSON string and FEN for the current state
    moves = Column(Text, default="[]") 
    current_fen = Column(String, default="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    white = relationship("User", foreign_keys=[white_id])
    black = relationship("User", foreign_keys=[black_id])
    
    
    #challenge
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
    
    
    #gameman
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
    
    
    #transactions
    
    import uuid
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from db import Base 




class Wallet(Base):
    __tablename__ = "wallets"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    balance = Column(Numeric(12, 2), default=0)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    amount = Column(Numeric(12, 2), nullable=False)
    type = Column(String(20), nullable=False)
    # DEPOSIT | WITHDRAWAL | WIN | LOSS

    reference = Column(String(255), unique=True, nullable=True)
    status = Column(String(20), default="PENDING")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
   
#users
from sqlalchemy import Column, Integer, String, Numeric, DateTime
from sqlalchemy.sql import func
from db import Base

class User(Base):
    __tablename__ = "users"
   
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    displayName = Column(String, nullable=False)
    password = Column(String, nullable=False)
    
   
    balance = Column(Numeric(12, 2), default=0.00)
    
    # Stats fields required by your profile logic
    avatarUrl = Column(String, nullable=True)
    gamesPlayed = Column(Integer, default=0)
    gamesWon = Column(Integer, default=0)
    currentRating = Column(Integer, default=1200)
    
    createdAt = Column(DateTime(timezone=True), server_default=func.now())
    updatedAt = Column(DateTime(timezone=True), onupdate=func.now())