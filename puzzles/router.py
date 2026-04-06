from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.auth import get_current_user_id
from core.database import get_db
from puzzles.schemas import (
    PuzzleAdvanceRequest,
    PuzzleCompleteRequest,
    PuzzleHintRequest,
    PuzzleMoveRequest,
    PuzzleRetryRequest,
)
from puzzles.service import (
    advance_session,
    complete_attempt,
    get_history,
    get_remaining,
    get_session,
    get_stats,
    request_hint,
    retry_attempt,
    submit_move,
)

router = APIRouter(tags=["Puzzles"])


@router.get("/session")
def puzzle_session(
    mode: str = "mixed",
    allowed_themes: list[str] | None = None,
    excluded_themes: list[str] | None = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return get_session(
        db,
        user_id,
        mode=mode,
        allowed_themes=allowed_themes,
        excluded_themes=excluded_themes,
    )


@router.get("/history")
def puzzle_history(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return get_history(db, user_id)


@router.get("/stats")
def puzzle_stats(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return get_stats(db, user_id)


@router.get("/remaining")
def puzzle_remaining(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return get_remaining(db, user_id)


@router.get("/queue/today")
def today_queue(
    mode: str = "mixed",
    allowed_themes: list[str] | None = None,
    excluded_themes: list[str] | None = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return get_session(
        db,
        user_id,
        mode=mode,
        allowed_themes=allowed_themes,
        excluded_themes=excluded_themes,
    )


@router.post("/session/move")
def move_on_puzzle(
    payload: PuzzleMoveRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return submit_move(db, user_id, attempt_id=payload.attempt_id, move=payload.move)


@router.post("/session/next")
def next_puzzle(
    payload: PuzzleAdvanceRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return advance_session(
        db,
        user_id,
        attempt_id=payload.attempt_id,
        skip_active=payload.skip_active,
        mode=payload.mode,
        allowed_themes=payload.allowed_themes,
        excluded_themes=payload.excluded_themes,
    )


@router.post("/session/hint")
def hint_for_puzzle(
    payload: PuzzleHintRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return request_hint(db, user_id, attempt_id=payload.attempt_id)


@router.post("/session/retry")
def retry_active_puzzle(
    payload: PuzzleRetryRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return retry_attempt(db, user_id, attempt_id=payload.attempt_id)


@router.post("/session/complete")
def complete_puzzle(
    payload: PuzzleCompleteRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return complete_attempt(
        db,
        user_id,
        attempt_id=payload.attempt_id,
        outcome=payload.outcome,
    )
