from __future__ import annotations

from core.ratings import (
    determine_rating_category,
    expected_score,
    get_user_rating,
    k_factor_for_player,
    normalize_time_control,
    recompute_overall_rating,
    result_score,
    set_user_rating,
)


def build_game_rating_payload(game) -> dict[str, int | bool | str | None]:
    return {
        "isRated": bool(getattr(game, "is_rated", True)),
        "ratingCategory": getattr(game, "rating_category", "blitz"),
        "timeControl": getattr(game, "time_control", "5+0"),
        "applied": bool(getattr(game, "rating_applied", False)),
        "whiteBefore": getattr(game, "white_rating_before", None),
        "blackBefore": getattr(game, "black_rating_before", None),
        "whiteAfter": getattr(game, "white_rating_after", None),
        "blackAfter": getattr(game, "black_rating_after", None),
        "whiteChange": getattr(game, "white_rating_change", None),
        "blackChange": getattr(game, "black_rating_change", None),
    }


def initialize_game_rating_snapshot(game, white_player, black_player):
    game.time_control = normalize_time_control(getattr(game, "time_control", None))
    game.rating_category = determine_rating_category(game.time_control)

    white_before = get_user_rating(white_player, game.rating_category)
    black_before = get_user_rating(black_player, game.rating_category)

    game.white_rating_before = white_before
    game.black_rating_before = black_before
    game.white_rating_after = white_before
    game.black_rating_after = black_before
    game.white_rating_change = 0
    game.black_rating_change = 0

    return build_game_rating_payload(game)


def _apply_activity_counters(game, white_player, black_player) -> None:
    white_player.games_played = int(getattr(white_player, "games_played", 0) or 0) + 1
    black_player.games_played = int(getattr(black_player, "games_played", 0) or 0) + 1

    if getattr(game, "result", None) == "WHITE_WIN":
        white_player.games_won = int(getattr(white_player, "games_won", 0) or 0) + 1
    elif getattr(game, "result", None) == "BLACK_WIN":
        black_player.games_won = int(getattr(black_player, "games_won", 0) or 0) + 1


def apply_game_result(game, white_player, black_player):
    if getattr(game, "rating_applied", False):
        return build_game_rating_payload(game)

    if game.white_rating_before is None or game.black_rating_before is None:
        initialize_game_rating_snapshot(game, white_player, black_player)

    _apply_activity_counters(game, white_player, black_player)

    if not bool(getattr(game, "is_rated", True)):
        game.white_rating_after = game.white_rating_before
        game.black_rating_after = game.black_rating_before
        game.white_rating_change = 0
        game.black_rating_change = 0
        game.rating_applied = True
        return build_game_rating_payload(game)

    white_before = int(game.white_rating_before)
    black_before = int(game.black_rating_before)
    white_score, black_score = result_score(getattr(game, "result", None))
    white_expected = expected_score(white_before, black_before)
    black_expected = expected_score(black_before, white_before)

    white_delta = round(k_factor_for_player(white_player, white_before) * (white_score - white_expected))
    black_delta = round(k_factor_for_player(black_player, black_before) * (black_score - black_expected))

    white_after = set_user_rating(white_player, game.rating_category, white_before + white_delta)
    black_after = set_user_rating(black_player, game.rating_category, black_before + black_delta)

    white_player.rated_games_played = int(getattr(white_player, "rated_games_played", 0) or 0) + 1
    black_player.rated_games_played = int(getattr(black_player, "rated_games_played", 0) or 0) + 1
    recompute_overall_rating(white_player)
    recompute_overall_rating(black_player)

    game.white_rating_after = white_after
    game.black_rating_after = black_after
    game.white_rating_change = white_after - white_before
    game.black_rating_change = black_after - black_before
    game.rating_applied = True

    return build_game_rating_payload(game)
