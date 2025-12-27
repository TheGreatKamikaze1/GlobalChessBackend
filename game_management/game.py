from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
import json
from datetime import datetime

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


# Helpers

def get_game_or_404(db: Session, game_id: int) -> Game:
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"success": False, "error": {"code": "GAME_NOT_FOUND", "message": "Game not found"}},
        )
    return game


def check_participant(game: Game, user_id: int):
    if user_id not in (game.white_id, game.black_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"success": False, "error": {"code": "FORBIDDEN", "message": "Not a participant"}},
        )


def get_current_turn(moves: list[str]) -> str:
    return "white" if len(moves) % 2 == 0 else "black"


# Routes

@router.get("/{game_id}", response_model=GameResponse)
def get_game(game_id: int, db: Session = Depends(get_db)):
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
        "moves": json.loads(game.moves),
        "currentFen": game.current_fen,
        "startedAt": game.started_at,
        "result": game.result,
        "completedAt": game.completed_at,
    }


@router.post("/{game_id}/move", response_model=MoveResponse)
def make_move(
    game_id: int,
    req: MoveRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    result = process_move(db, game_id, user_id, req.move)

    if "error" in result:
        error_map = {
            "GAME_NOT_ACTIVE": (400, "Game not active"),
            "NOT_YOUR_TURN": (403, "Not your turn"),
            "ILLEGAL_MOVE": (400, "Illegal move"),
            "INVALID_FORMAT": (400, "Invalid move format"),
        }
        status_code, msg = error_map.get(result["error"], (400, "Move failed"))
        raise HTTPException(status_code=status_code, detail=msg)

    return {
        "gameId": game_id,
        "move": req.move,
        "currentFen": result["fen"],
        "isCheck": result.get("isCheck", False),
        "isCheckmate": result.get("isCheckmate", False),
        "isGameOver": result["gameOver"],
    }


@router.post("/{game_id}/resign", response_model=ResignResponse)
def resign_game(
    game_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    game = get_game_or_404(db, game_id)
    check_participant(game, user_id)

    if game.status != "ONGOING":
        raise HTTPException(status_code=400, detail="Game already ended")

    winner_id = game.black_id if user_id == game.white_id else game.white_id
    result = "BLACK_WIN" if user_id == game.white_id else "WHITE_WIN"

    game.status = "COMPLETED"
    game.result = result
    game.winner_id = winner_id
    game.completed_at = datetime.utcnow()

    db.query(User).filter(User.id == winner_id).update({
        User.balance: User.balance + (game.stake * 2)
    })

    db.commit()

    return {
        "gameId": game_id,
        "result": result,
        "winnerId": winner_id,
        "message": "You resigned. Game over.",
    }


@router.get("/history", response_model=PaginatedHistory)
def get_game_history(
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    base_filter = [
        or_(Game.white_id == user_id, Game.black_id == user_id),
        Game.status == "COMPLETED",
    ]

    total = db.query(Game).filter(*base_filter).count()
    games = db.query(Game).filter(*base_filter).offset(params.offset).limit(params.limit).all()

    data = []
    for game in games:
        opponent = game.black if game.white_id == user_id else game.white
        data.append(GameHistoryItem(
            id=game.id,
            opponent=PlayerDetails(
                id=opponent.id,
                username=opponent.username,
                displayName=opponent.display_name,
            ),
            stake=game.stake,
            result=game.result,
            moveCount=len(json.loads(game.moves)),
            completedAt=game.completed_at,
        ))

    return {"success": True, "data": data, "pagination": {"total": total, **params.dict()}}


@router.get("/active", response_model=ActiveGamesResponse)
def get_active_games(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    games = db.query(Game).filter(
        or_(Game.white_id == user_id, Game.black_id == user_id),
        Game.status == "ONGOING",
    ).all()

    data = []
    for game in games:
        opponent = game.black if game.white_id == user_id else game.white
        data.append(ActiveGameItem(
            id=game.id,
            opponent=PlayerDetails(
                id=opponent.id,
                username=opponent.username,
                displayName=opponent.display_name,
            ),
            stake=game.stake,
            status=game.status,
            startedAt=game.started_at,
            currentTurn=get_current_turn(json.loads(game.moves)),
        ))

    return {"success": True, "data": data}
