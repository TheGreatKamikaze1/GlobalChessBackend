from __future__ import annotations

from typing import Literal


DEFAULT_RATING = 1200
RATING_FLOOR = 100
RATING_CATEGORIES = ("bullet", "blitz", "rapid", "classical")
RatingCategory = Literal["bullet", "blitz", "rapid", "classical"]


def normalize_time_control(time_control: str | None) -> str:
    raw = (time_control or "").strip()
    if not raw:
        return "5+0"

    if "+" in raw:
        base, increment = raw.split("+", 1)
    elif "/" in raw:
        base, increment = raw.split("/", 1)
    else:
        try:
            numeric = int(raw)
        except ValueError:
            return "5+0"

        if numeric <= 60:
            return f"{numeric}+0"
        minutes = max(1, round(numeric / 60))
        return f"{minutes}+0"

    try:
        base_minutes = max(1, int(base))
    except ValueError:
        base_minutes = 5

    try:
        increment_seconds = max(0, int(increment))
    except ValueError:
        increment_seconds = 0

    return f"{base_minutes}+{increment_seconds}"


def parse_time_control(time_control: str | None) -> tuple[int, int]:
    normalized = normalize_time_control(time_control)
    base, increment = normalized.split("+", 1)
    return int(base) * 60, int(increment)


def determine_rating_category(time_control: str | None) -> RatingCategory:
    base_seconds, increment_seconds = parse_time_control(time_control)
    estimated_seconds = base_seconds + (increment_seconds * 40)

    if estimated_seconds < 180:
        return "bullet"
    if estimated_seconds < 480:
        return "blitz"
    if estimated_seconds < 1500:
        return "rapid"
    return "classical"


def rating_field_for_category(category: RatingCategory) -> str:
    return f"{category}_rating"


def get_user_rating(user, category: RatingCategory) -> int:
    value = getattr(user, rating_field_for_category(category), None)
    if value is None:
        return int(getattr(user, "current_rating", DEFAULT_RATING) or DEFAULT_RATING)
    return int(value)


def set_user_rating(user, category: RatingCategory, value: int) -> int:
    bounded = max(RATING_FLOOR, int(round(value)))
    setattr(user, rating_field_for_category(category), bounded)
    return bounded


def get_rating_snapshot(user) -> dict[str, int]:
    bullet = int(getattr(user, "bullet_rating", DEFAULT_RATING) or DEFAULT_RATING)
    blitz = int(getattr(user, "blitz_rating", DEFAULT_RATING) or DEFAULT_RATING)
    rapid = int(getattr(user, "rapid_rating", DEFAULT_RATING) or DEFAULT_RATING)
    classical = int(getattr(user, "classical_rating", DEFAULT_RATING) or DEFAULT_RATING)
    overall = int(getattr(user, "current_rating", DEFAULT_RATING) or DEFAULT_RATING)

    return {
        "overall": overall,
        "bullet": bullet,
        "blitz": blitz,
        "rapid": rapid,
        "classical": classical,
    }


def recompute_overall_rating(user) -> int:
    snapshot = get_rating_snapshot(user)
    overall = round(
        (snapshot["bullet"] + snapshot["blitz"] + snapshot["rapid"] + snapshot["classical"]) / 4
    )
    user.current_rating = int(overall)
    return int(overall)


def k_factor_for_player(user, rating_value: int) -> int:
    rated_games_played = int(getattr(user, "rated_games_played", 0) or 0)

    if rated_games_played < 30:
        return 40
    if rating_value >= 2400:
        return 10
    if rating_value >= 2000:
        return 16
    return 24


def expected_score(player_rating: int, opponent_rating: int) -> float:
    return 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))


def result_score(result: str | None) -> tuple[float, float]:
    if result == "WHITE_WIN":
        return 1.0, 0.0
    if result == "BLACK_WIN":
        return 0.0, 1.0
    return 0.5, 0.5
