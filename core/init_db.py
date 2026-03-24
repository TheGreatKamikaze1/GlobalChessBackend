import time
from sqlalchemy.exc import OperationalError

from core.database import engine
from core.models import Base


NON_RETRYABLE_DB_ERRORS = (
    "password authentication failed",
    "server does not support ssl",
    "database does not exist",
    "role does not exist",
    "no pg_hba.conf entry",
)


def _is_retryable_db_error(error: OperationalError) -> bool:
    message = str(error).lower()
    return not any(fragment in message for fragment in NON_RETRYABLE_DB_ERRORS)


def init_db():
    print("Creating database tables...")

    for attempt in range(1, 8):
        try:
            Base.metadata.create_all(bind=engine)
            print("Done.")
            return
        except OperationalError as e:
            if not _is_retryable_db_error(e):
                raise RuntimeError(f"Database configuration error: {e}") from e
            print(f"[init_db] DB not ready (attempt {attempt}/7): {e}")
            time.sleep(min(2 * attempt, 10))

    raise RuntimeError("Database not reachable after retries. Startup aborted.")
