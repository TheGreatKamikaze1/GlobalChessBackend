import time
from sqlalchemy.exc import OperationalError

from core.database import engine
from core.models import Base

def init_db():
    print("Creating database tables...")

    
    for attempt in range(1, 8):  
        try:
            Base.metadata.create_all(bind=engine)
            print("Done.")
            return
        except OperationalError as e:
            print(f"[init_db] DB not ready (attempt {attempt}/7): {e}")
            time.sleep(min(2 * attempt, 10))

   
    raise RuntimeError("Database not reachable after retries. Startup aborted.")
