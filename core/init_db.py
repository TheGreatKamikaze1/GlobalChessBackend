import time
from sqlalchemy.exc import OperationalError

from core.database import engine
from core.models import Base


def reset_db():
    print("Resetting database tables...")

    for attempt in range(1, 8):
        try:
            # Drop all tables first
            Base.metadata.drop_all(bind=engine)
            print("Existing tables dropped.")

            # Recreate all tables
            Base.metadata.create_all(bind=engine)
            print("Fresh tables created.")
            return

        except OperationalError as e:
            print(f"[reset_db] DB not ready (attempt {attempt}/7): {e}")
            time.sleep(min(2 * attempt, 10))

    raise RuntimeError("Database not reachable after retries. Startup aborted.")