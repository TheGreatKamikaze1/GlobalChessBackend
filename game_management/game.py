from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
import json
from datetime import datetime, timezone
import re
from core.database import get_db
from core.models import Game, User
from core.ratings import determine_rating_category, get_user_rating, normalize_time_control
from game_management.dependencies import get_current_user_id_dep
from game_management.logic import process_move
from game_management.ratings import apply_game_result, build_game_rating_payload
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
    PremoveRequest,
    RatingState,
)

router = APIRouter(tags=["Games"])

_UCI_RE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$", re.IGNORECASE)


def _same_user(left: str | None, right: str | None) -> bool:
    return str(left or "") == str(right or "")


def get_game_or_404(db: Session, game_id: str) -> Game:
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


def check_participant(game: Game, user_id: str):
    if not any(_same_user(user_id, participant_id) for participant_id in (game.white_id, game.black_id)):
        raise HTTPException(status_code=403, detail="Not a participant")


def get_current_turn(moves: list[str]) -> str:
    return "white" if len(moves) % 2 == 0 else "black"


def _game_time_control(game: Game) -> str:
    challenge_time_control = getattr(getattr(game, "challenge", None), "time_control", None)
    return normalize_time_control(getattr(game, "time_control", None) or challenge_time_control)


def _game_rating_category(game: Game) -> str:
    return getattr(game, "rating_category", None) or determine_rating_category(_game_time_control(game))


def _player_details(user, game: Game, color: str) -> PlayerDetails:
    rating_category = _game_rating_category(game)
    fallback_rating = get_user_rating(user, rating_category)
    before_rating = getattr(game, f"{color}_rating_before", None)

    return PlayerDetails(
        id=str(user.id),
        username=user.username,
        displayName=user.display_name,
        rating=int(before_rating if before_rating is not None else fallback_rating),
    )


def _rating_state(game: Game) -> RatingState:
    payload = build_game_rating_payload(game)
    payload["timeControl"] = _game_time_control(game)
    payload["ratingCategory"] = _game_rating_category(game)
    return RatingState(**payload)


@router.get("/history", response_model=PaginatedHistory)
def game_history(
    limit: int = Query(10, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id_dep),
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
        player_color = "white" if g.white_id == user_id else "black"
        opponent_color = "black" if player_color == "white" else "white"
        opponent_rating = getattr(g, f"{opponent_color}_rating_before", None)
        if opponent_rating is None:
            opponent_rating = get_user_rating(opponent, _game_rating_category(g))
        player_rating_before = getattr(g, f"{player_color}_rating_before", None)
        player_rating_after = getattr(g, f"{player_color}_rating_after", None)
        player_rating_change = getattr(g, f"{player_color}_rating_change", None)

        items.append(
                GameHistoryItem(
                    id=str(g.id),
                    opponent=PlayerDetails(
                        id=str(opponent.id),
                        username=opponent.username,
                        displayName=opponent.display_name,
                        rating=int(opponent_rating),
                    ),
                    stake=0.0,
                    timeControl=_game_time_control(g),
                    isRated=bool(getattr(g, "is_rated", True)),
                    ratingCategory=_game_rating_category(g),
                    playerRatingBefore=player_rating_before,
                    playerRatingAfter=player_rating_after,
                    playerRatingChange=player_rating_change,
                    result=result,
                    moveCount=len(moves),
                    completedAt=g.completed_at,
                )
        )

    return {
        "success": True,
        "data": items,
        "pagination": {"limit": limit, "offset": offset, "total": total},
    }


@router.get("/active", response_model=ActiveGamesResponse)
def active_games(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id_dep),
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
        player_color = "white" if _same_user(g.white_id, user_id) else "black"
        opponent = g.black if player_color == "white" else g.white
        moves = json.loads(g.moves or "[]")
        current_turn = get_current_turn(moves)
        opponent_color = "black" if player_color == "white" else "white"
        opponent_rating = getattr(g, f"{opponent_color}_rating_before", None)
        if opponent_rating is None:
            opponent_rating = get_user_rating(opponent, _game_rating_category(g))

        items.append(
                ActiveGameItem(
                    id=str(g.id),
                    challengeId=str(g.challenge_id) if g.challenge_id else None,
                    opponent=PlayerDetails(
                        id=str(opponent.id),
                        username=opponent.username,
                        displayName=opponent.display_name,
                        rating=int(opponent_rating),
                    ),
                    stake=0.0,
                    timeControl=_game_time_control(g),
                    isRated=bool(getattr(g, "is_rated", True)),
                    ratingCategory=_game_rating_category(g),
                    status=g.status,
                    startedAt=g.started_at,
                    currentTurn=current_turn,
                    playerColor=player_color,
                    yourTurn=current_turn == player_color,
                )
        )

    return {"success": True, "data": items}


@router.get("/all")
def all_games(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id_dep),
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
                "stake": 0.0,
                "result": result,
                "date": date,
                "moves": len(moves),
            }
        )

    return {"success": True, "data": response}


@router.post("/{game_id}/premove")
def set_or_cancel_premove(
    game_id: str,
    payload: PremoveRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id_dep),
):
    game = db.query(Game).filter(Game.id == game_id).with_for_update().first()
    if not game:
        raise HTTPException(404, "Game not found")

    if game.status != "ONGOING":
        raise HTTPException(400, "Game not active")

    check_participant(game, user_id)

    move = (payload.move or "").strip()
    if move == "":
        move = None

    is_white = (user_id == game.white_id)

    if move is None:
        if is_white:
            game.premove_white = None
        else:
            game.premove_black = None
        db.commit()
        return {"success": True, "message": "Premove cancelled"}

    if not _UCI_RE.match(move):
        raise HTTPException(400, "Invalid premove format. Use UCI like e2e4")

    move = move.lower()

    if is_white:
        game.premove_white = move
    else:
        game.premove_black = move

    db.commit()
    return {"success": True, "message": "Premove set", "move": move}


@router.get("/{game_id}/premove")
def get_my_premove(
    game_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id_dep),
):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(404, "Game not found")

    check_participant(game, user_id)

    is_white = (user_id == game.white_id)
    move = game.premove_white if is_white else game.premove_black
    return {"success": True, "data": {"move": move}}




@router.get("/{game_id}", response_model=GameResponse)
def get_game(game_id: str, db: Session = Depends(get_db)):
    game = get_game_or_404(db, game_id)
    moves = json.loads(game.moves or "[]")

    return {
        "id": str(game.id),
        "challengeId": str(game.challenge_id) if game.challenge_id else None,
        "white": _player_details(game.white, game, "white"),
        "black": _player_details(game.black, game, "black"),
        "stake": 0.0,
        "timeControl": _game_time_control(game),
        "isRated": bool(getattr(game, "is_rated", True)),
        "ratingCategory": _game_rating_category(game),
        "rating": _rating_state(game),
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
    user_id: str = Depends(get_current_user_id_dep),
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
        if err == "PLAYER_NOT_FOUND":
            raise HTTPException(status_code=404, detail=err)
        raise HTTPException(status_code=400, detail=err)

    return {
        "gameId": game_id,
        "uci": result["uci"],
        "san": result["san"],
        "currentFen": result["fen"],
        "isCheck": result["isCheck"],
        "isCheckmate": result["isCheckmate"],
        "isGameOver": result["gameOver"],
        "rating": result.get("rating"),
        "result": result.get("result"),
        "winnerId": result.get("winnerId"),
    }


@router.post("/{game_id}/resign", response_model=ResignResponse)
def resign_game(
    game_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id_dep),
):
    game = db.query(Game).filter(Game.id == game_id).with_for_update().first()
    if not game:
        raise HTTPException(404, "Game not found")

    check_participant(game, user_id)

    if game.status != "ONGOING":
        raise HTTPException(400, "Game already ended")

    winner_id = game.black_id if user_id == game.white_id else game.white_id
    result = "BLACK_WIN" if user_id == game.white_id else "WHITE_WIN"
    white_player = db.query(User).filter(User.id == game.white_id).with_for_update().first()
    black_player = db.query(User).filter(User.id == game.black_id).with_for_update().first()

    if not white_player or not black_player:
        raise HTTPException(404, "Player not found")

    game.status = "COMPLETED"
    game.result = result
    game.winner_id = winner_id
    game.completed_at = datetime.now(timezone.utc)
    rating_payload = apply_game_result(game, white_player, black_player)

    db.commit()

    return {
        "gameId": game_id,
        "result": result,
        "winnerId": winner_id,
        "message": "You resigned. Game over.",
        "rating": rating_payload,
    }
