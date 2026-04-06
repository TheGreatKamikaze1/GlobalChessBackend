from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import chess
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.models import PuzzleAttempt, PuzzleQueue
from puzzles.catalog import (
    PUZZLE_CATALOG,
    get_filtered_catalog,
    get_puzzle_by_id,
    puzzle_difficulty_label,
    stable_puzzle_hash,
)

DAILY_LIMIT = 20
DEFAULT_PUZZLE_RATING = 1200
MIN_PUZZLE_RATING = 600
MAX_PUZZLE_RATING = 2400


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _today_queue_key() -> str:
    return _utc_now().date().isoformat()


def _json_loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def _queue_puzzle_ids(queue: PuzzleQueue) -> list[str]:
    return [str(value) for value in _json_loads(queue.puzzle_ids, [])]


def _attempt_played_line(attempt: PuzzleAttempt) -> list[str]:
    return [str(value) for value in _json_loads(attempt.played_line, [])]


def _serialize_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def _player_color_for_puzzle(puzzle: dict[str, Any]) -> bool:
    return chess.Board(puzzle["playable_fen"]).turn


def _clamp_rating(value: int) -> int:
    return max(MIN_PUZZLE_RATING, min(MAX_PUZZLE_RATING, value))


def _current_puzzle_rating(
    db: Session,
    user_id: str,
    *,
    exclude_attempt_id: str | None = None,
) -> int:
    query = db.query(func.coalesce(func.sum(PuzzleAttempt.rating_delta), 0)).filter(
        PuzzleAttempt.user_id == user_id,
        PuzzleAttempt.completed_at.isnot(None),
    )
    if exclude_attempt_id:
        query = query.filter(PuzzleAttempt.id != exclude_attempt_id)
    total_delta = int(query.scalar() or 0)
    return _clamp_rating(DEFAULT_PUZZLE_RATING + total_delta)


def _current_streak(db: Session, user_id: str) -> int:
    attempts = (
        db.query(PuzzleAttempt.status)
        .filter(
            PuzzleAttempt.user_id == user_id,
            PuzzleAttempt.completed_at.isnot(None),
        )
        .order_by(PuzzleAttempt.completed_at.desc())
        .limit(200)
        .all()
    )

    streak = 0
    for (status,) in attempts:
        if status == "solved":
            streak += 1
            continue
        break
    return streak


def _latest_completed_attempt(db: Session, user_id: str) -> PuzzleAttempt | None:
    return (
        db.query(PuzzleAttempt)
        .filter(
            PuzzleAttempt.user_id == user_id,
            PuzzleAttempt.completed_at.isnot(None),
        )
        .order_by(PuzzleAttempt.completed_at.desc())
        .first()
    )


def _latest_queue(db: Session, user_id: str, queue_date: str) -> PuzzleQueue | None:
    return (
        db.query(PuzzleQueue)
        .filter(PuzzleQueue.user_id == user_id, PuzzleQueue.queue_date == queue_date)
        .first()
    )


def _latest_attempt_for_queue(db: Session, queue_id: str) -> PuzzleAttempt | None:
    return (
        db.query(PuzzleAttempt)
        .filter(PuzzleAttempt.queue_id == queue_id)
        .order_by(PuzzleAttempt.queue_position.desc(), PuzzleAttempt.served_at.desc())
        .first()
    )


def _queue_history_attempts(db: Session, user_id: str) -> list[PuzzleAttempt]:
    return (
        db.query(PuzzleAttempt)
        .filter(PuzzleAttempt.user_id == user_id)
        .order_by(PuzzleAttempt.served_at.desc())
        .limit(40)
        .all()
    )


def _mode_target_rating(base_rating: int, mode: str) -> int:
    if mode == "easy":
        return max(MIN_PUZZLE_RATING, base_rating - 180)
    if mode == "hard":
        return min(MAX_PUZZLE_RATING, base_rating + 180)
    return base_rating


def _selection_key(
    puzzle: dict[str, Any],
    *,
    user_id: str,
    queue_date: str,
    mode: str,
    target_rating: int,
) -> tuple[int, str]:
    distance = 0 if mode == "mixed" else abs(int(puzzle["rating"]) - target_rating)
    return (
        distance,
        stable_puzzle_hash(user_id, queue_date, mode, str(puzzle["id"])),
    )


def _select_queue_puzzles(
    db: Session,
    user_id: str,
    *,
    queue_date: str,
    mode: str,
    allowed_themes: list[str] | None = None,
    excluded_themes: list[str] | None = None,
) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    current_rating = _current_puzzle_rating(db, user_id)
    target_rating = _mode_target_rating(current_rating, mode)

    catalog = get_filtered_catalog(allowed_themes, excluded_themes)
    if not catalog:
        catalog = list(PUZZLE_CATALOG)

    recent_attempt_ids = {
        attempt.puzzle_id
        for attempt in (
            db.query(PuzzleAttempt)
            .filter(PuzzleAttempt.user_id == user_id)
            .order_by(PuzzleAttempt.served_at.desc())
            .limit(40)
            .all()
        )
    }

    fresh = [puzzle for puzzle in catalog if puzzle["id"] not in recent_attempt_ids]
    stale = [puzzle for puzzle in catalog if puzzle["id"] in recent_attempt_ids]

    sort_kwargs = {
        "user_id": user_id,
        "queue_date": queue_date,
        "mode": mode,
        "target_rating": target_rating,
    }
    fresh.sort(key=lambda puzzle: _selection_key(puzzle, **sort_kwargs))
    stale.sort(key=lambda puzzle: _selection_key(puzzle, **sort_kwargs))

    selected = fresh[:DAILY_LIMIT]
    if len(selected) < DAILY_LIMIT:
        for puzzle in stale:
            if puzzle not in selected:
                selected.append(puzzle)
            if len(selected) >= DAILY_LIMIT:
                break

    summary: dict[str, Any] = {
        "catalog": "starter-local",
        "requested_mode": mode,
        "target_rating": target_rating,
        "selected_count": len(selected),
        "fresh_count": len([p for p in selected if p["id"] not in recent_attempt_ids]),
        "difficulty_mix": {
            "easy": sum(1 for puzzle in selected if puzzle["rating"] < 1100),
            "normal": sum(1 for puzzle in selected if 1100 <= puzzle["rating"] < 1500),
            "hard": sum(1 for puzzle in selected if puzzle["rating"] >= 1500),
        },
    }

    return selected, current_rating, summary


def _compute_solution_san_line(puzzle: dict[str, Any]) -> list[str]:
    board = chess.Board(puzzle["playable_fen"])
    line: list[str] = []
    for uci in puzzle["solution_moves"]:
        move = chess.Move.from_uci(uci)
        line.append(board.san(move))
        board.push(move)
    return line


def _active_hint_payload(puzzle: dict[str, Any], attempt: PuzzleAttempt) -> dict[str, Any] | None:
    if not attempt.active_hint_level or attempt.progress_ply >= len(puzzle["solution_moves"]):
        return None

    board = chess.Board(attempt.position_fen)
    expected_move = chess.Move.from_uci(puzzle["solution_moves"][attempt.progress_ply])
    san = board.san(expected_move)
    piece = board.piece_at(expected_move.from_square)
    piece_name = chess.piece_name(piece.piece_type) if piece else "piece"
    from_square = chess.square_name(expected_move.from_square)
    to_square = chess.square_name(expected_move.to_square)

    if attempt.active_hint_level == 1:
        return {
            "level": 1,
            "hint_type": "piece",
            "message": f"Start with the {piece_name} from {from_square}.",
            "from_square": from_square,
            "to_square": None,
            "move_uci": None,
            "move_san": None,
        }
    if attempt.active_hint_level == 2:
        return {
            "level": 2,
            "hint_type": "square",
            "message": f"Look closely at the route from {from_square} to {to_square}.",
            "from_square": from_square,
            "to_square": to_square,
            "move_uci": None,
            "move_san": None,
        }
    return {
        "level": 3,
        "hint_type": "move",
        "message": f"The tactic lands with {san}.",
        "from_square": from_square,
        "to_square": to_square,
        "move_uci": expected_move.uci(),
        "move_san": san,
    }


def _elapsed_seconds(attempt: PuzzleAttempt) -> int:
    end_time = attempt.completed_at or _utc_now()
    start_time = attempt.served_at
    if not start_time:
        return 0
    return max(0, int((end_time - start_time).total_seconds()))


def _serialize_puzzle_descriptor(puzzle: dict[str, Any]) -> dict[str, Any]:
    board = chess.Board(puzzle["playable_fen"])
    side = "white" if board.turn == chess.WHITE else "black"
    return {
        "id": puzzle["id"],
        "source_puzzle_id": puzzle["source_puzzle_id"],
        "playable_fen": puzzle["playable_fen"],
        "rating": puzzle["rating"],
        "rating_deviation": puzzle["rating_deviation"],
        "popularity": puzzle["popularity"],
        "nb_plays": puzzle["nb_plays"],
        "move_count": len(puzzle["solution_moves"]),
        "difficulty_label": puzzle_difficulty_label(int(puzzle["rating"])),
        "game_url": puzzle["game_url"],
        "side_to_move": side,
        "orientation": side,
        "revealed_themes": puzzle["revealed_themes"],
        "opening_tags": puzzle["opening_tags"],
    }


def _serialize_attempt(puzzle: dict[str, Any], attempt: PuzzleAttempt) -> dict[str, Any]:
    reveal_line = _compute_solution_san_line(puzzle) if attempt.status != "served" else []
    return {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "progress_ply": attempt.progress_ply,
        "position_fen": attempt.position_fen,
        "feedback": attempt.feedback,
        "last_move": attempt.last_move,
        "mistakes": attempt.mistakes,
        "hints_used": attempt.hints_used,
        "retry_count": attempt.retry_count,
        "first_attempt_correct": attempt.first_attempt_correct,
        "elapsed_seconds": _elapsed_seconds(attempt),
        "played_line": _attempt_played_line(attempt),
        "reveal_line": reveal_line,
        "active_hint": _active_hint_payload(puzzle, attempt),
        "puzzle": _serialize_puzzle_descriptor(puzzle),
    }


def _serialize_history_item(puzzle: dict[str, Any], attempt: PuzzleAttempt) -> dict[str, Any]:
    return {
        "attempt_id": attempt.id,
        "puzzle_id": attempt.puzzle_id,
        "source_puzzle_id": attempt.source_puzzle_id,
        "status": attempt.status,
        "served_at": attempt.served_at,
        "completed_at": attempt.completed_at,
        "queue_date": attempt.served_at.date().isoformat() if attempt.served_at else _today_queue_key(),
        "rating": puzzle["rating"],
        "move_count": len(puzzle["solution_moves"]),
        "mistakes": attempt.mistakes,
        "hints_used": attempt.hints_used,
        "retry_count": attempt.retry_count,
        "time_spent_seconds": _elapsed_seconds(attempt),
        "rating_delta": attempt.rating_delta,
        "first_attempt_correct": attempt.first_attempt_correct,
        "revealed_themes": puzzle["revealed_themes"],
    }


def _serialize_queue(queue: PuzzleQueue) -> dict[str, Any]:
    return {
        "id": queue.id,
        "queue_date": queue.queue_date,
        "mode": queue.mode,
        "total_count": queue.total_count,
        "consumed_count": queue.consumed_count,
        "remaining_count": max(0, queue.total_count - queue.consumed_count),
        "generated_at": queue.generated_at,
        "target_rating": queue.target_rating,
        "selection_summary": _json_loads(queue.selection_summary, {}),
    }


def _stats_payload(db: Session, user_id: str, queue: PuzzleQueue) -> dict[str, Any]:
    today_attempts = (
        db.query(PuzzleAttempt)
        .filter(PuzzleAttempt.queue_id == queue.id)
        .order_by(PuzzleAttempt.served_at.desc())
        .all()
    )
    current_rating = _current_puzzle_rating(db, user_id)
    latest_completed = _latest_completed_attempt(db, user_id)

    total_solved = (
        db.query(func.count(PuzzleAttempt.id))
        .filter(PuzzleAttempt.user_id == user_id, PuzzleAttempt.status == "solved")
        .scalar()
        or 0
    )
    total_failed = (
        db.query(func.count(PuzzleAttempt.id))
        .filter(PuzzleAttempt.user_id == user_id, PuzzleAttempt.status == "failed")
        .scalar()
        or 0
    )

    solved_today = sum(1 for attempt in today_attempts if attempt.status == "solved")
    failed_today = sum(1 for attempt in today_attempts if attempt.status == "failed")
    skipped_today = sum(1 for attempt in today_attempts if attempt.status == "skipped")

    return {
        "daily_limit": queue.total_count,
        "served_today": queue.consumed_count,
        "remaining_today": max(0, queue.total_count - queue.consumed_count),
        "solved_today": solved_today,
        "failed_today": failed_today,
        "skipped_today": skipped_today,
        "current_streak": _current_streak(db, user_id),
        "total_solved": int(total_solved),
        "total_failed": int(total_failed),
        "current_puzzle_rating": current_rating,
        "last_rating_delta": latest_completed.rating_delta if latest_completed else 0,
    }


def _session_payload(
    db: Session,
    user_id: str,
    queue: PuzzleQueue,
    current_attempt: PuzzleAttempt | None,
    *,
    notice: str | None = None,
) -> dict[str, Any]:
    history_items = []
    for attempt in _queue_history_attempts(db, user_id):
        puzzle = get_puzzle_by_id(attempt.puzzle_id)
        if puzzle:
            history_items.append(_serialize_history_item(puzzle, attempt))

    current_payload = None
    if current_attempt:
        puzzle = get_puzzle_by_id(current_attempt.puzzle_id)
        if puzzle:
            current_payload = _serialize_attempt(puzzle, current_attempt)

    limit_reached = (
        queue.consumed_count >= queue.total_count
        and (current_attempt is None or current_attempt.status != "served")
    )

    return {
        "queue": _serialize_queue(queue),
        "current": current_payload,
        "recent_history": history_items,
        "stats": _stats_payload(db, user_id, queue),
        "limit_reached": limit_reached,
        "notice": notice,
    }


def ensure_daily_queue(
    db: Session,
    user_id: str,
    *,
    mode: str = "mixed",
    allowed_themes: list[str] | None = None,
    excluded_themes: list[str] | None = None,
) -> tuple[PuzzleQueue, str | None]:
    queue_date = _today_queue_key()
    existing_queue = _latest_queue(db, user_id, queue_date)
    if existing_queue:
        notice = None
        if mode and mode != existing_queue.mode:
            notice = f"Today's queue is already locked to {existing_queue.mode.upper()} mode."
        return existing_queue, notice

    selected_puzzles, current_rating, selection_summary = _select_queue_puzzles(
        db,
        user_id,
        queue_date=queue_date,
        mode=mode,
        allowed_themes=allowed_themes,
        excluded_themes=excluded_themes,
    )

    queue = PuzzleQueue(
        user_id=user_id,
        queue_date=queue_date,
        mode=mode,
        total_count=len(selected_puzzles),
        consumed_count=0,
        target_rating=current_rating,
        selection_summary=_serialize_json(selection_summary),
        puzzle_ids=_serialize_json([puzzle["id"] for puzzle in selected_puzzles]),
    )
    db.add(queue)
    db.commit()
    db.refresh(queue)
    return queue, "Local starter puzzle bank is active for this queue."


def get_session(
    db: Session,
    user_id: str,
    *,
    mode: str = "mixed",
    allowed_themes: list[str] | None = None,
    excluded_themes: list[str] | None = None,
) -> dict[str, Any]:
    queue, notice = ensure_daily_queue(
        db,
        user_id,
        mode=mode,
        allowed_themes=allowed_themes,
        excluded_themes=excluded_themes,
    )
    current_attempt = _latest_attempt_for_queue(db, queue.id)
    return _session_payload(db, user_id, queue, current_attempt, notice=notice)


def get_history(db: Session, user_id: str) -> dict[str, Any]:
    items = []
    for attempt in _queue_history_attempts(db, user_id):
        puzzle = get_puzzle_by_id(attempt.puzzle_id)
        if puzzle:
            items.append(_serialize_history_item(puzzle, attempt))
    return {"items": items}


def get_stats(db: Session, user_id: str) -> dict[str, Any]:
    queue, _ = ensure_daily_queue(db, user_id)
    return {"stats": _stats_payload(db, user_id, queue)}


def get_remaining(db: Session, user_id: str) -> dict[str, Any]:
    queue, _ = ensure_daily_queue(db, user_id)
    return {
        "daily_limit": queue.total_count,
        "served_today": queue.consumed_count,
        "remaining_today": max(0, queue.total_count - queue.consumed_count),
        "queue_id": queue.id,
        "total_in_queue": queue.total_count,
        "consumed_count": queue.consumed_count,
    }


def _attempt_or_404(db: Session, user_id: str, attempt_id: str) -> PuzzleAttempt:
    attempt = (
        db.query(PuzzleAttempt)
        .filter(PuzzleAttempt.id == attempt_id, PuzzleAttempt.user_id == user_id)
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Puzzle attempt not found")
    return attempt


def _mark_attempt_complete(
    db: Session,
    attempt: PuzzleAttempt,
    *,
    status: str,
    feedback: str,
    rating_delta: int = 0,
) -> None:
    attempt.status = status
    attempt.feedback = feedback
    attempt.completed_at = _utc_now()
    attempt.rating_delta = rating_delta
    attempt.active_hint_level = None
    db.commit()
    db.refresh(attempt)


def _solve_rating_delta(current_rating: int, puzzle_rating: int, hints_used: int) -> int:
    base = 12 + round((puzzle_rating - current_rating) / 120)
    penalty = min(4, hints_used * 2)
    return max(6, min(20, base - penalty))


def _fail_rating_delta(current_rating: int, puzzle_rating: int) -> int:
    base = 10 + round((current_rating - puzzle_rating) / 140)
    return -max(6, min(18, base))


def _start_next_attempt(db: Session, user_id: str, queue: PuzzleQueue) -> PuzzleAttempt | None:
    if queue.consumed_count >= queue.total_count:
        return _latest_attempt_for_queue(db, queue.id)

    puzzle_ids = _queue_puzzle_ids(queue)
    next_puzzle_id = puzzle_ids[queue.consumed_count]
    puzzle = get_puzzle_by_id(next_puzzle_id)
    if not puzzle:
        raise HTTPException(status_code=500, detail="Puzzle catalog entry is missing")

    attempt = PuzzleAttempt(
        user_id=user_id,
        queue_id=queue.id,
        queue_position=queue.consumed_count,
        puzzle_id=str(puzzle["id"]),
        source_puzzle_id=str(puzzle["source_puzzle_id"]),
        status="served",
        progress_ply=0,
        position_fen=str(puzzle["playable_fen"]),
        feedback="Play the tactic from the shown position.",
        last_move=None,
        mistakes=0,
        hints_used=0,
        retry_count=0,
        first_attempt_correct=True,
        rating_delta=0,
        active_hint_level=None,
        played_line="[]",
    )
    db.add(attempt)
    queue.consumed_count += 1
    db.commit()
    db.refresh(queue)
    db.refresh(attempt)
    return attempt


def advance_session(
    db: Session,
    user_id: str,
    *,
    attempt_id: str | None = None,
    skip_active: bool = False,
    mode: str = "mixed",
    allowed_themes: list[str] | None = None,
    excluded_themes: list[str] | None = None,
) -> dict[str, Any]:
    queue, notice = ensure_daily_queue(
        db,
        user_id,
        mode=mode,
        allowed_themes=allowed_themes,
        excluded_themes=excluded_themes,
    )
    current_attempt = _latest_attempt_for_queue(db, queue.id)

    if attempt_id and current_attempt and current_attempt.id != attempt_id:
        current_attempt = _attempt_or_404(db, user_id, attempt_id)

    if current_attempt and current_attempt.status == "served":
        if not skip_active:
            raise HTTPException(status_code=400, detail="Finish or skip the active puzzle first")
        _mark_attempt_complete(
            db,
            current_attempt,
            status="skipped",
            feedback="Puzzle skipped. The next position is ready when you are.",
            rating_delta=0,
        )

    next_attempt = _start_next_attempt(db, user_id, queue)
    return _session_payload(db, user_id, queue, next_attempt, notice=notice)


def submit_move(db: Session, user_id: str, *, attempt_id: str, move: str) -> dict[str, Any]:
    attempt = _attempt_or_404(db, user_id, attempt_id)
    if attempt.status != "served":
        raise HTTPException(status_code=400, detail="This puzzle is no longer active")

    puzzle = get_puzzle_by_id(attempt.puzzle_id)
    if not puzzle:
        raise HTTPException(status_code=404, detail="Puzzle definition not found")

    solution_moves = list(puzzle["solution_moves"])
    if attempt.progress_ply >= len(solution_moves):
        raise HTTPException(status_code=400, detail="Puzzle line is already complete")

    expected_uci = solution_moves[attempt.progress_ply]
    if move != expected_uci:
        attempt.mistakes += 1
        attempt.first_attempt_correct = False
        attempt.last_move = move
        current_rating = _current_puzzle_rating(db, user_id, exclude_attempt_id=attempt.id)
        rating_delta = _fail_rating_delta(current_rating, int(puzzle["rating"]))
        _mark_attempt_complete(
            db,
            attempt,
            status="failed",
            feedback="That move misses the tactic. Review the solution and continue.",
            rating_delta=rating_delta,
        )
        queue = db.query(PuzzleQueue).filter(PuzzleQueue.id == attempt.queue_id).first()
        return _session_payload(db, user_id, queue, attempt)

    board = chess.Board(attempt.position_fen)
    player_color = _player_color_for_puzzle(puzzle)
    played_line = _attempt_played_line(attempt)

    while attempt.progress_ply < len(solution_moves):
        next_uci = solution_moves[attempt.progress_ply]
        next_move = chess.Move.from_uci(next_uci)

        if attempt.progress_ply == len(played_line):
            san = board.san(next_move)
        else:
            san = board.san(next_move)

        board.push(next_move)
        played_line.append(san)
        attempt.last_move = next_uci
        attempt.progress_ply += 1

        if board.turn == player_color:
            break

    attempt.position_fen = board.fen()
    attempt.played_line = _serialize_json(played_line)
    attempt.feedback = "Correct move."
    attempt.active_hint_level = None

    if attempt.progress_ply >= len(solution_moves):
        current_rating = _current_puzzle_rating(db, user_id, exclude_attempt_id=attempt.id)
        rating_delta = _solve_rating_delta(current_rating, int(puzzle["rating"]), attempt.hints_used)
        _mark_attempt_complete(
            db,
            attempt,
            status="solved",
            feedback="Nice finish. You found the winning move.",
            rating_delta=rating_delta,
        )
    else:
        db.commit()
        db.refresh(attempt)

    queue = db.query(PuzzleQueue).filter(PuzzleQueue.id == attempt.queue_id).first()
    return _session_payload(db, user_id, queue, attempt)


def request_hint(db: Session, user_id: str, *, attempt_id: str) -> dict[str, Any]:
    attempt = _attempt_or_404(db, user_id, attempt_id)
    if attempt.status != "served":
        raise HTTPException(status_code=400, detail="Hints are only available on active puzzles")

    attempt.hints_used += 1
    attempt.active_hint_level = min(3, max(1, attempt.hints_used))
    attempt.feedback = "Hint revealed. Try the idea on the board."
    db.commit()
    db.refresh(attempt)

    queue = db.query(PuzzleQueue).filter(PuzzleQueue.id == attempt.queue_id).first()
    return _session_payload(db, user_id, queue, attempt)


def retry_attempt(db: Session, user_id: str, *, attempt_id: str) -> dict[str, Any]:
    attempt = _attempt_or_404(db, user_id, attempt_id)
    if attempt.status != "served":
        raise HTTPException(status_code=400, detail="Only active puzzles can be reset")

    puzzle = get_puzzle_by_id(attempt.puzzle_id)
    if not puzzle:
        raise HTTPException(status_code=404, detail="Puzzle definition not found")

    attempt.position_fen = puzzle["playable_fen"]
    attempt.progress_ply = 0
    attempt.feedback = "Puzzle reset. Start again from the initial position."
    attempt.last_move = None
    attempt.retry_count += 1
    attempt.active_hint_level = None
    attempt.played_line = "[]"
    db.commit()
    db.refresh(attempt)

    queue = db.query(PuzzleQueue).filter(PuzzleQueue.id == attempt.queue_id).first()
    return _session_payload(db, user_id, queue, attempt)


def complete_attempt(
    db: Session,
    user_id: str,
    *,
    attempt_id: str,
    outcome: str = "reviewed",
) -> dict[str, Any]:
    attempt = _attempt_or_404(db, user_id, attempt_id)
    if attempt.status == "served" and outcome == "skipped":
        _mark_attempt_complete(
            db,
            attempt,
            status="skipped",
            feedback="Puzzle skipped.",
            rating_delta=0,
        )

    queue = db.query(PuzzleQueue).filter(PuzzleQueue.id == attempt.queue_id).first()
    latest_attempt = _latest_attempt_for_queue(db, queue.id)
    return _session_payload(db, user_id, queue, latest_attempt)
