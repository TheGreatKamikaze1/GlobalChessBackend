from __future__ import annotations

import time

from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from core.database import SessionLocal, engine
from core.models import Base, Challenge, Game, User
from core.ratings import (
    determine_rating_category,
    get_rating_snapshot,
    normalize_time_control,
    recompute_overall_rating,
)

SCHEMA_PATCHES: dict[str, dict[str, str]] = {
    "users": {
        "rated_games_played": "INTEGER NOT NULL DEFAULT 0",
        "bullet_rating": "INTEGER NOT NULL DEFAULT 1200",
        "blitz_rating": "INTEGER NOT NULL DEFAULT 1200",
        "rapid_rating": "INTEGER NOT NULL DEFAULT 1200",
        "classical_rating": "INTEGER NOT NULL DEFAULT 1200",
    },
    "challenges": {
        "is_rated": "BOOLEAN NOT NULL DEFAULT TRUE",
    },
    "games": {
        "time_control": "VARCHAR NOT NULL DEFAULT '5+0'",
        "rating_category": "VARCHAR NOT NULL DEFAULT 'blitz'",
        "is_rated": "BOOLEAN NOT NULL DEFAULT TRUE",
        "rating_applied": "BOOLEAN NOT NULL DEFAULT FALSE",
        "white_rating_before": "INTEGER",
        "black_rating_before": "INTEGER",
        "white_rating_after": "INTEGER",
        "black_rating_after": "INTEGER",
        "white_rating_change": "INTEGER",
        "black_rating_change": "INTEGER",
    },
}


def _ensure_schema_columns() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table_name, columns in SCHEMA_PATCHES.items():
            if table_name not in existing_tables:
                continue

            for column_name, ddl in columns.items():
                connection.execute(
                    text(
                        f'ALTER TABLE "{table_name}" '
                        f'ADD COLUMN IF NOT EXISTS "{column_name}" {ddl}'
                    )
                )


def _backfill_rating_state() -> None:
    db = SessionLocal()

    try:
        for user in db.query(User).all():
            current_rating = int(getattr(user, "current_rating", 1200) or 1200)

            if getattr(user, "bullet_rating", None) is None:
                user.bullet_rating = current_rating
            if getattr(user, "blitz_rating", None) is None:
                user.blitz_rating = current_rating
            if getattr(user, "rapid_rating", None) is None:
                user.rapid_rating = current_rating
            if getattr(user, "classical_rating", None) is None:
                user.classical_rating = current_rating

            recompute_overall_rating(user)

        for challenge in db.query(Challenge).all():
            if getattr(challenge, "time_control", None):
                challenge.time_control = normalize_time_control(challenge.time_control)
            if getattr(challenge, "is_rated", None) is None:
                challenge.is_rated = True

        for game in db.query(Game).all():
            challenge = getattr(game, "challenge", None)
            challenge_time_control = getattr(challenge, "time_control", None)
            challenge_is_rated = getattr(challenge, "is_rated", None)

            game.time_control = normalize_time_control(game.time_control or challenge_time_control)
            game.rating_category = determine_rating_category(game.time_control)

            if getattr(game, "is_rated", None) is None:
                game.is_rated = True if challenge_is_rated is None else bool(challenge_is_rated)

            if game.status != "ONGOING":
                continue

            if game.white and game.white_rating_before is None:
                game.white_rating_before = get_rating_snapshot(game.white)[game.rating_category]
            if game.black and game.black_rating_before is None:
                game.black_rating_before = get_rating_snapshot(game.black)[game.rating_category]

            if game.white_rating_after is None:
                game.white_rating_after = game.white_rating_before
            if game.black_rating_after is None:
                game.black_rating_after = game.black_rating_before

            if game.white_rating_change is None:
                game.white_rating_change = 0
            if game.black_rating_change is None:
                game.black_rating_change = 0

        db.commit()
    finally:
        db.close()


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


def init_db() -> None:
    print("Creating database tables...")

    for attempt in range(1, 8):
        try:
            Base.metadata.create_all(bind=engine)
            _ensure_schema_columns()
            _backfill_rating_state()
            print("Done.")
            return
        except OperationalError as exc:
            if not _is_retryable_db_error(exc):
                raise RuntimeError(f"Database configuration error: {exc}") from exc
            print(f"[init_db] DB not ready (attempt {attempt}/7): {exc}")
            time.sleep(min(2 * attempt, 10))

    raise RuntimeError("Database not reachable after retries. Startup aborted.")


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _ensure_schema_columns()
    _backfill_rating_state()
