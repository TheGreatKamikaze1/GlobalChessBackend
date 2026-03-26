import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine import make_url

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_PUBLIC_URL or DATABASE_URL is not set")

parsed_url = make_url(DATABASE_URL)
db_host = parsed_url.host

if parsed_url.drivername.startswith("postgresql") and not db_host:
    raise ValueError(
        "DATABASE_URL is missing a database host. "
        "Set DATABASE_PUBLIC_URL or DATABASE_URL to a full Postgres URL."
    )

connect_args = {
    "connect_timeout": 10,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
}

if parsed_url.drivername.startswith("postgresql") and db_host not in {"localhost", "127.0.0.1", "::1"}:
    connect_args["sslmode"] = "require"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
