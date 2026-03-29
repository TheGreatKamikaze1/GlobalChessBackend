from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.init_db import reset_db


def main() -> None:
    if "--force" not in sys.argv:
        print("Refusing to reset the database without --force.")
        print("Run: python scripts/reset_database.py --force")
        raise SystemExit(1)

    print("Dropping all backend tables and recreating a fresh schema...")
    reset_db()
    print("Database reset complete.")


if __name__ == "__main__":
    main()
