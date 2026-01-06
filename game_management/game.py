from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
import json
from datetime import datetime
from datetime import timezone

from core.database import get_db
from core.models import Game, User
from game_management.dependencies import get_current_user_id
from game_management.logic import process_move
from game_management.game_schema import (
    GameResponse,
    MoveRequest,
    MoveResponse,
    ResignResponse,
    PaginationParams,
    PaginatedHistory,
    ActiveGamesResponse,
    PlayerDetails,
    GameHistoryItem,
    ActiveGameItem,
)

router = APIRouter(tags=["Games"])


def get_game_or_404(db: Session, game_id: str) -> Game:
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(
            status_code=404,
            detail={"success": False, "error": {"code": "GAME_NOT_FOUND", "message": "Game not found"}},
        )
    return game


def check_participant(game: Game, user_id: str):
    if user_id not in (game.white_id, game.black_id):
        raise HTTPException(
            status_code=403,
            detail={"success": False, "error": {"code": "FORBIDDEN", "message": "Not a participant"}},
        )


def get_current_turn(moves: list[str]) -> str:
    return "white" if len(moves) % 2 == 0 else "black"


@router.get("/{game_id}", response_model=GameResponse)
def get_game(game_id: str, db: Session = Depends(get_db)):
    game = get_game_or_404(db, game_id)

    return {
        "id": game.id,
        "white": PlayerDetails(
            id=game.white.id,
            username=game.white.username,
            displayName=game.white.display_name,
        ),
        "black": PlayerDetails(
            id=game.black.id,
            username=game.black.username,
            displayName=game.black.display_name,
        ),
        "stake": game.stake,
        "status": game.status,
        "moves": json.loads(game.moves or "[]"),
        "currentFen": game.current_fen,
        "startedAt": game.started_at,
        "result": game.result,
        "completedAt": game.completed_at,
    }


@router.post("/{game_id}/move", response_model=MoveResponse)
def make_move(
    game_id: str,
    req: MoveRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = process_move(db, game_id, user_id, req.move)

    if "error" in result:
        error_map = {
            "GAME_NOT_ACTIVE": (400, "Game not active"),
            "NOT_YOUR_TURN": (403, "Not your turn"),
            "ILLEGAL_MOVE": (400, "Illegal move"),
            "INVALID_FORMAT": (400, "Invalid move format"),
            "NOT_PARTICIPANT": (403, "Not a participant"),
        }
        code, msg = error_map.get(result["error"], (400, "Move failed"))
        raise HTTPException(code, msg)

    return {
        "gameId": game_id,
        "move": req.move,
        "currentFen": result["fen"],
        "isCheck": False,
        "isCheckmate": False,
        "isGameOver": result["gameOver"],
    }


@router.post("/{game_id}/resign", response_model=ResignResponse)
def resign_game(
    game_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    game = (
        db.query(Game)
        .filter(Game.id == game_id)
        .with_for_update()
        .first()
    )

    if not game:
        raise HTTPException(404, "Game not found")

    check_participant(game, user_id)

    if game.status != "ONGOING":
        raise HTTPException(400, "Game already ended")

    winner_id = game.black_id if user_id == game.white_id else game.white_id
    result = "BLACK_WIN" if user_id == game.white_id else "WHITE_WIN"

    game.status = "COMPLETED"
    game.result = result
    game.winner_id = winner_id
    game.completed_at = datetime.now(timezone.utc)

    winner = db.query(User).filter(User.id == winner_id).with_for_update().first()
    winner.balance += (game.stake * 2)

    db.commit()

    return {
        "gameId": game_id,
        "result": result,
        "winnerId": winner_id,
        "message": "You resigned. Game over.",
    }
