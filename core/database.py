import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Production logic: Always pull from environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/chess_db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
        
        #db.py
        from sqlalchemy import create_engine, Column, Integer, String
