from __future__ import annotations

import hashlib
from typing import Any


PuzzleDefinition = dict[str, Any]


def _entry(
    source_id: str,
    fen: str,
    move: str,
    rating: int,
    themes: list[str],
    opening_tags: list[str] | None = None,
) -> PuzzleDefinition:
    return {
        "id": source_id.lower(),
        "source_puzzle_id": source_id,
        "playable_fen": fen,
        "solution_moves": [move],
        "rating": rating,
        "rating_deviation": 75,
        "popularity": max(55, min(95, 95 - (rating - 800) // 25)),
        "nb_plays": 900 + rating,
        "revealed_themes": themes,
        "opening_tags": opening_tags or [],
        "game_url": "",
    }


PUZZLE_CATALOG: list[PuzzleDefinition] = [
    _entry("GC-1001", "k7/8/K7/8/8/8/8/Q7 w - - 0 1", "a1h8", 860, ["mateInOne", "queenMate", "edgeMate"]),
    _entry("GC-1002", "k7/8/K7/8/8/8/8/1Q6 w - - 0 1", "b1b7", 900, ["mateInOne", "queenMate", "fileMate"]),
    _entry("GC-1003", "k7/8/K7/8/8/8/8/2Q5 w - - 0 1", "c1c8", 940, ["mateInOne", "queenMate", "backRankMate"]),
    _entry("GC-1004", "k7/8/K7/8/8/8/8/3Q4 w - - 0 1", "d1d8", 980, ["mateInOne", "queenMate", "backRankMate"]),
    _entry("GC-1005", "k7/8/K7/8/8/8/8/4Q3 w - - 0 1", "e1e8", 1020, ["mateInOne", "queenMate", "longRange"]),
    _entry("GC-1006", "k7/8/K7/8/8/8/8/5Q2 w - - 0 1", "f1f8", 1060, ["mateInOne", "queenMate", "longRange"]),
    _entry("GC-1007", "k7/8/K7/8/8/8/Q7/8 w - - 0 1", "a2g8", 1100, ["mateInOne", "queenMate", "diagonalMate"]),
    _entry("GC-1008", "k7/8/1K6/8/8/1Q6/8/8 w - - 0 1", "b3g8", 1140, ["mateInOne", "queenMate", "diagonalMate"]),
    _entry("GC-1009", "k7/8/K7/8/8/8/8/2R5 w - - 0 1", "c1c8", 1180, ["mateInOne", "rookMate", "backRankMate"]),
    _entry("GC-1010", "k7/8/K7/8/8/8/8/3R4 w - - 0 1", "d1d8", 1220, ["mateInOne", "rookMate", "backRankMate"]),
    _entry("GC-1011", "k7/8/K7/8/8/8/8/4R3 w - - 0 1", "e1e8", 1260, ["mateInOne", "rookMate", "longRange"]),
    _entry("GC-1012", "k7/8/K7/8/8/8/8/5R2 w - - 0 1", "f1f8", 1300, ["mateInOne", "rookMate", "longRange"]),
    _entry("GC-1013", "k7/8/K7/8/8/8/8/6R1 w - - 0 1", "g1g8", 1340, ["mateInOne", "rookMate", "fileMate"]),
    _entry("GC-1014", "k7/8/K7/8/8/8/8/7R w - - 0 1", "h1h8", 1380, ["mateInOne", "rookMate", "fileMate"]),
    _entry("GC-1015", "k7/8/K7/8/8/8/2R5/8 w - - 0 1", "c2c8", 1420, ["mateInOne", "rookMate", "backRankMate"]),
    _entry("GC-1016", "k7/8/K7/8/8/8/7R/8 w - - 0 1", "h2h8", 1460, ["mateInOne", "rookMate", "fileMate"]),
    _entry("GC-1017", "K7/8/k7/8/8/8/8/1q6 b - - 0 1", "b1b7", 1500, ["mateInOne", "queenMate", "blackToMove"]),
    _entry("GC-1018", "K7/8/k7/8/8/8/8/2q5 b - - 0 1", "c1c8", 1540, ["mateInOne", "queenMate", "blackToMove"]),
    _entry("GC-1019", "K7/8/k7/8/8/8/8/4q3 b - - 0 1", "e1e8", 1580, ["mateInOne", "queenMate", "blackToMove"]),
    _entry("GC-1020", "K7/8/k7/8/8/q7/8/8 b - - 0 1", "a3f8", 1620, ["mateInOne", "queenMate", "blackToMove", "diagonalMate"]),
    _entry("GC-1021", "K7/8/k7/8/8/8/8/2r5 b - - 0 1", "c1c8", 1660, ["mateInOne", "rookMate", "blackToMove"]),
    _entry("GC-1022", "K7/8/k7/8/8/8/8/4r3 b - - 0 1", "e1e8", 1700, ["mateInOne", "rookMate", "blackToMove"]),
    _entry("GC-1023", "K7/8/k7/8/8/8/6r1/8 b - - 0 1", "g2g8", 1740, ["mateInOne", "rookMate", "blackToMove", "fileMate"]),
    _entry("GC-1024", "K7/8/k7/8/8/8/7r/8 b - - 0 1", "h2h8", 1780, ["mateInOne", "rookMate", "blackToMove", "fileMate"]),
]

PUZZLES_BY_ID: dict[str, PuzzleDefinition] = {
    puzzle["id"]: puzzle for puzzle in PUZZLE_CATALOG
}


def puzzle_difficulty_label(rating: int) -> str:
    if rating < 1100:
        return "Easy"
    if rating < 1500:
        return "Normal"
    return "Hard"


def stable_puzzle_hash(user_id: str, queue_date: str, mode: str, puzzle_id: str) -> str:
    value = f"{queue_date}|{user_id}|{mode}|{puzzle_id}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def get_puzzle_by_id(puzzle_id: str) -> PuzzleDefinition | None:
    return PUZZLES_BY_ID.get(puzzle_id)


def get_filtered_catalog(
    allowed_themes: list[str] | None = None,
    excluded_themes: list[str] | None = None,
) -> list[PuzzleDefinition]:
    allowed = {theme.strip() for theme in allowed_themes or [] if theme.strip()}
    excluded = {theme.strip() for theme in excluded_themes or [] if theme.strip()}

    puzzles: list[PuzzleDefinition] = []
    for puzzle in PUZZLE_CATALOG:
        themes = set(puzzle["revealed_themes"])
        if allowed and not (themes & allowed):
            continue
        if excluded and themes & excluded:
            continue
        puzzles.append(puzzle)
    return puzzles
