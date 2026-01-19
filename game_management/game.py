from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
import json
from datetime import datetime, timezone

from core.database import get_db
from core.models import Game, User
from game_management.dependencies import get_current_user_id_dep
from game_management.logic import process_move
from game_management.game_schema import (
    GameResponse,
    MoveRequest,
    MoveResponse,
    ResignResponse,
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
        raise HTTPException(status_code=404, detail="Game not found")
    return game


def check_participant(game: Game, user_id: int):
    if user_id not in (game.white_id, game.black_id):
        raise HTTPException(status_code=403, detail="Not a participant")


def get_current_turn(moves: list[str]) -> str:
    
    return "white" if len(moves) % 2 == 0 else "black"



@router.get("/history", response_model=PaginatedHistory)
def game_history(
    limit: int = Query(10, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id_dep),
):
    query = (
        db.query(Game)
        .filter(
            or_(Game.white_id == user_id, Game.black_id == user_id),
            Game.status == "COMPLETED",
        )
        .order_by(Game.completed_at.desc())
    )

    total = query.count()
    games = query.offset(offset).limit(limit).all()

    items = []
    for g in games:
        opponent = g.black if g.white_id == user_id else g.white
        result = (
            "DRAW"
            if g.result == "DRAW"
            else "WIN"
            if g.winner_id == user_id
            else "LOSS"
        )

        moves = json.loads(g.moves or "[]")

        items.append(
            GameHistoryItem(
                id=str(g.id),
                opponent=PlayerDetails(
                    id=str(opponent.id),
                    username=opponent.username,
                    displayName=opponent.display_name,
                ),
                stake=float(g.stake),
                result=result,
                moveCount=len(moves),
                completedAt=g.completed_at,
            )
        )

    return {
        "success": True,
        "data": items,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
        },
    }


@router.get("/active", response_model=ActiveGamesResponse)
def active_games(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id_dep),
):
    games = (
        db.query(Game)
        .filter(
            or_(Game.white_id == user_id, Game.black_id == user_id),
            Game.status == "ONGOING",
        )
        .order_by(Game.started_at.desc())
        .all()
    )

    items = []
    for g in games:
        opponent = g.black if g.white_id == user_id else g.white
        moves = json.loads(g.moves or "[]")

        items.append(
            ActiveGameItem(
                id=str(g.id),
                opponent=PlayerDetails(
                    id=str(opponent.id),
                    username=opponent.username,
                    displayName=opponent.display_name,
                ),
                stake=float(g.stake),
                status=g.status,
                startedAt=g.started_at,
                currentTurn=get_current_turn(moves),
            )
        )

    return {"success": True, "data": items}


@router.get("/all")
def all_games(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id_dep),
):
    games = (
        db.query(Game)
        .filter(or_(Game.white_id == user_id, Game.black_id == user_id))
        .order_by(Game.started_at.desc())
        .all()
    )

    response = []

    for g in games:
        opponent = g.black if g.white_id == user_id else g.white
        moves = json.loads(g.moves or "[]")

        if g.status == "ONGOING":
            result = "ongoing"
            date = g.started_at
        else:
            if g.result == "DRAW":
                result = "draw"
            elif g.winner_id == user_id:
                result = "won"
            else:
                result = "lost"
            date = g.completed_at

        response.append(
            {
                "id": str(g.id),
                "opponent": opponent.username,
                "stake": float(g.stake),
                "result": result,
                "date": date,
                "moves": len(moves),
            }
        )

    return {"success": True, "data": response}




@router.get("/{game_id}", response_model=GameResponse)
def get_game(game_id: str, db: Session = Depends(get_db)):
    game = get_game_or_404(db, game_id)
    moves = json.loads(game.moves or "[]")

    return {
        "id": str(game.id),
        "white": PlayerDetails(
            id=str(game.white.id),
            username=game.white.username,
            displayName=game.white.display_name,
        ),
        "black": PlayerDetails(
            id=str(game.black.id),
            username=game.black.username,
            displayName=game.black.display_name,
        ),
        "stake": float(game.stake),
        "status": game.status,
        "moves": moves,
        "currentFen": (game.current_fen or "").strip() or "startpos",
        "startedAt": game.started_at,
        "currentTurn": get_current_turn(moves),
        "result": game.result,
        "completedAt": game.completed_at,
    }


@router.post("/{game_id}/move", response_model=MoveResponse)
def make_move(
    game_id: str,
    req: MoveRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id_dep),
):
    result = process_move(db, game_id, user_id, req.move)

    if "error" in result:
        err = result["error"]
        if err == "GAME_NOT_FOUND":
            raise HTTPException(status_code=404, detail=err)
        if err == "NOT_PARTICIPANT":
            raise HTTPException(status_code=403, detail=err)
        if err == "NOT_YOUR_TURN":
            raise HTTPException(status_code=409, detail=err)
        raise HTTPException(status_code=400, detail=err)

    return {
        "gameId": game_id,
        "uci": result["uci"],
        "san": result["san"],
        "currentFen": result["fen"],
        "isCheck": result["isCheck"],
        "isCheckmate": result["isCheckmate"],
        "isGameOver": result["gameOver"],
        "result": result.get("result"),
        "winnerId": result.get("winnerId"),
    }


@router.post("/{game_id}/resign", response_model=ResignResponse)
def resign_game(
    game_id: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id_dep),
):
    game = db.query(Game).filter(Game.id == game_id).with_for_update().first()
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
    if winner:
        winner.balance += game.stake * 2

    db.commit()

    return {
        "gameId": game_id,
        "result": result,
        "winnerId": winner_id,
        "message": "You resigned. Game over.",
    }
