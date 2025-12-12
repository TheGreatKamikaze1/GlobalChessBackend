
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base
import os


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://myuser:Admin@localhost:5432/auth_db")

engine = create_engine(DATABASE_URL, future=True)


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()