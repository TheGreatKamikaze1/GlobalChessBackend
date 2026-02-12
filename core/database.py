import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv(".env")


DATABASE_URL = (
    os.getenv("DATABASE_PUBLIC_URL")
    or os.getenv("DATABASE_URL")
)

if not DATABASE_URL:
    raise ValueError("DATABASE_URL (or DATABASE_PUBLIC_URL) is not set in the environment")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
