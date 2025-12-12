from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
import json

from db import get_db
from models import Game, User
from dependencies import get_current_user_id

from game_schema import (
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

router = APIRouter()


# -------------------------------
# Helpers
# -------------------------------

def get_game_or_404(db: Session, game_id: int) -> Game:
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"success": False, "error": {"code": "GAME_NOT_FOUND", "message": "Game not found"}},
        )
    return game


def check_participant(game: Game, user_id: int):
    if game.white_id != user_id and game.black_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"success": False, "error": {"code": "FORBIDDEN", "message": "You are not a participant"}},
        )


def get_current_turn(moves: list[str]) -> str:
    return "white" if len(moves) % 2 == 0 else "black"


# -------------------------------
# GET /game/{id}
# -------------------------------

@router.get("/{game_id}", response_model=GameResponse)
def get_game(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).filter(Game.id == game_id).first()

    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"success": False, "error": {"code": "GAME_NOT_FOUND", "message": "Game not found"}},
        )

    # Build user structures
    white_player = PlayerDetails(
        id=game.white.id,
        username=game.white.username,
        displayName=game.white.display_name,
    )
    black_player = PlayerDetails(
        id=game.black.id,
        username=game.black.username,
        displayName=game.black.display_name,
    )

    return {
        "id": game.id,
        "white": white_player,
        "black": black_player,
        "stake": game.stake,
        "status": game.status,
        "moves": json.loads(game.moves),
        "currentFen": game.current_fen,
        "startedAt": game.started_at,
        "result": game.result,
        "completedAt": game.completed_at,
    }


# -------------------------------
# POST /game/{id}/move
# -------------------------------

@router.post("/{game_id}/move", response_model=MoveResponse)
def make_move(
    game_id: int,
    req: MoveRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    game = get_game_or_404(db, game_id)
    check_participant(game, user_id)

    if game.status != "ONGOING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "error": {"code": "GAME_ALREADY_ENDED", "message": "Game already ended"}},
        )

    moves_list = json.loads(game.moves)

   
    move_str = req.move
    moves_list.append(move_str)

    db.query(Game).filter(Game.id == game_id).update({
        "moves": json.dumps(moves_list)
    })
    db.commit()

    return {
        "gameId": game_id,
        "move": move_str,
        "currentFen": game.current_fen, 
        "isCheck": False,
        "isCheckmate": False,
        "isGameOver": False,
    }


# -------------------------------
# POST /game/{id}/resign
# -------------------------------

@router.post("/{game_id}/resign", response_model=ResignResponse)
def resign_game(
    game_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    game = get_game_or_404(db, game_id)
    check_participant(game, user_id)

    if game.status != "ONGOING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "error": {"code": "GAME_ALREADY_ENDED", "message": "Game already ended"}},
        )

    # winner based on who resigned
    winner_id = game.black_id if game.white_id == user_id else game.white_id
    result = "BLACK_WIN" if game.white_id == user_id else "WHITE_WIN"

    try:
        
        db.query(Game).filter(Game.id == game_id).update({
            "status": "COMPLETED",
            "result": result,
            "winner_id": winner_id,
            "completed_at": datetime.utcnow(),
        })

        # update balances
        db.query(User).filter(User.id == winner_id).update({
            User.balance: User.balance + game.stake
        })
        db.query(User).filter(User.id == user_id).update({
            User.balance: User.balance - game.stake
        })

        db.commit()

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Transaction failed on resign"
        )

    return {
        "gameId": game_id,
        "result": result,
        "winnerId": winner_id,
        "message": "You have resigned. Game over.",
    }


# -------------------------------
# GET /game/history
# -------------------------------

@router.get("/history", response_model=PaginatedHistory)
def get_game_history(
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    limit = params.limit
    offset = params.offset

    base_filter = [
        or_(Game.white_id == user_id, Game.black_id == user_id),
        Game.status == "COMPLETED",
    ]

    total = db.query(Game).filter(*base_filter).count()
    games = db.query(Game).filter(*base_filter)\
        .offset(offset).limit(limit).all()

    data_list = []

    for game in games:
        # determine opponent
        opponent = game.black if game.white_id == user_id else game.white

        opponent_details = PlayerDetails(
            id=opponent.id,
            username=opponent.username,
            displayName=opponent.display_name,
        )

        data_list.append(GameHistoryItem(
            id=game.id,
            opponent=opponent_details,
            stake=game.stake,
            result=game.result,
            moveCount=len(json.loads(game.moves)),
            completedAt=game.completed_at,
        ))

    return {
        "success": True,
        "data": data_list,
        "pagination": {"total": total, "limit": limit, "offset": offset},
    }


# -------------------------------
# GET /game/active
# -------------------------------

@router.get("/active", response_model=ActiveGamesResponse)
def get_active_games(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    games = db.query(Game).filter(
        or_(Game.white_id == user_id, Game.black_id == user_id),
        Game.status == "ONGOING",
    ).all()

    data_list = []

    for game in games:
        opponent = game.black if game.white_id == user_id else game.white

        opponent_details = PlayerDetails(
            id=opponent.id,
            username=opponent.username,
            displayName=opponent.display_name,
        )

        current_turn = get_current_turn(json.loads(game.moves))

        data_list.append(ActiveGameItem(
            id=game.id,
            opponent=opponent_details,
            stake=game.stake,
            status=game.status,
            startedAt=game.started_at,
            currentTurn=current_turn,
        ))

    return {"success": True, "data": data_list}

