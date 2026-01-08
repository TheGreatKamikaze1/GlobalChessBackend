import chess
import json
from sqlalchemy.orm import Session
from core.models import Game, User
from datetime import datetime
from datetime import timezone


def process_move(db: Session, game_id: str, user_id: str, move_uci: str):

    game = db.query(Game).filter(Game.id == game_id).with_for_update().first()

    if not game or game.status != "ONGOING":
        return {"error": "GAME_NOT_ACTIVE"}

    if user_id not in (game.white_id, game.black_id):
        return {"error": "NOT_PARTICIPANT"}

    board = chess.Board(game.current_fen)

    is_white = (user_id == game.white_id)

    if (board.turn == chess.WHITE and not is_white) or (board.turn == chess.BLACK and is_white):
        return {"error": "NOT_YOUR_TURN"}

    try:
        move = chess.Move.from_uci(move_uci)
        if move not in board.legal_moves:
            return {"error": "ILLEGAL_MOVE"}
    except Exception:
        return {"error": "INVALID_FORMAT"}

    # apply move
    board.push(move)

    moves_list = json.loads(game.moves or "[]")
    moves_list.append(move_uci)

    game.current_fen = board.fen()
    game.moves = json.dumps(moves_list)

    game_over = board.is_game_over()

    if not game_over:
        db.commit()
        return {"success": True, "fen": game.current_fen, "gameOver": False}

    # --- GAME OVER HANDLING ---
    game.status = "COMPLETED"
    game.completed_at = datetime.now(timezone.utc)

    winner_id = None
    result = None

    if board.is_checkmate():
        if board.turn == chess.WHITE:
            # black delivered mate
            winner_id = game.black_id
            result = "BLACK_WIN"
        else:
            winner_id = game.white_id
            result = "WHITE_WIN"

        game.result = result
        game.winner_id = winner_id

        winner = db.query(User).filter(User.id == winner_id).with_for_update().first()
        winner.balance += (game.stake * 2)

    else:
        # draw (stalemate, repetition, insufficient material etc)
        game.result = "DRAW"
        db.query(User).filter(User.id.in_([game.white_id, game.black_id])).update(
            {User.balance: User.balance + game.stake},
            synchronize_session=False
        )

    db.commit()

    return {
        "success": True,
        "fen": game.current_fen,
        "gameOver": True,
        "result": game.result,
        "winnerId": winner_id
    }
