import chess
import json
from sqlalchemy.orm import Session
from core.models import Game, User
from datetime import datetime, timezone
import re


_UCI_RE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$", re.IGNORECASE)


def _load_moves(game: Game) -> list[str]:
    try:
        return json.loads(game.moves or "[]")
    except Exception:
        return []


def _starting_fen(game: Game) -> str:
    # Safe fallback if DB has NULL/empty fen for newly created games
    fen = (game.current_fen or "").strip()
    return fen if fen else chess.STARTING_FEN


def _parse_move(board: chess.Board, move_text: str) -> tuple[chess.Move, str, str]:
   
    s = move_text.strip()

    # If it looks like UCI, try UCI first
    if _UCI_RE.match(s):
        try:
            mv = chess.Move.from_uci(s.lower())
            if mv not in board.legal_moves:
                raise ValueError("illegal")
            san = board.san(mv)
            return mv, mv.uci(), san
        except Exception:
          
            pass

    # Try SAN
    try:
        mv = board.parse_san(s)
        uci = mv.uci()
        san = board.san(mv)
        return mv, uci, san
    except Exception:
        raise ValueError("invalid_format")


def process_move(db: Session, game_id: str, user_id: int, move_text: str):
    game = db.query(Game).filter(Game.id == game_id).with_for_update().first()

    if not game:
        return {"error": "GAME_NOT_FOUND"}

    if game.status != "ONGOING":
        return {"error": "GAME_NOT_ACTIVE"}

    if user_id not in (game.white_id, game.black_id):
        return {"error": "NOT_PARTICIPANT"}

    board = chess.Board(_starting_fen(game))

    is_white_player = (user_id == game.white_id)

    # enforce turn
    if (board.turn == chess.WHITE and not is_white_player) or (board.turn == chess.BLACK and is_white_player):
        return {"error": "NOT_YOUR_TURN"}

    # parse + validate move
    try:
        move, uci, san = _parse_move(board, move_text)
    except ValueError:
        return {"error": "INVALID_FORMAT_OR_ILLEGAL"}

    # apply move
    board.push(move)

    moves_list = _load_moves(game)
    moves_list.append(uci)

    game.current_fen = board.fen()
    game.moves = json.dumps(moves_list)

    is_check = board.is_check()
    is_checkmate = board.is_checkmate()
    game_over = board.is_game_over()

    if not game_over:
        db.commit()
        return {
            "success": True,
            "uci": uci,
            "san": san,
            "fen": game.current_fen,
            "isCheck": is_check,
            "isCheckmate": is_checkmate,
            "gameOver": False,
        }

    # --- GAME OVER HANDLING ---
    game.status = "COMPLETED"
    game.completed_at = datetime.now(timezone.utc)

    winner_id = None
    result = None

    if is_checkmate:
        
        if board.turn == chess.WHITE:
            winner_id = game.black_id
            result = "BLACK_WIN"
        else:
            winner_id = game.white_id
            result = "WHITE_WIN"

        game.result = result
        game.winner_id = winner_id

        winner = db.query(User).filter(User.id == winner_id).with_for_update().first()
        if winner:
            winner.balance += (game.stake * 2)
    else:
        # draw (stalemate, repetition, insufficient material, etc.)
        game.result = "DRAW"
        db.query(User).filter(User.id.in_([game.white_id, game.black_id])).update(
            {User.balance: User.balance + game.stake},
            synchronize_session=False,
        )

    db.commit()

    return {
        "success": True,
        "uci": uci,
        "san": san,
        "fen": game.current_fen,
        "isCheck": is_check,
        "isCheckmate": is_checkmate,
        "gameOver": True,
        "result": game.result,
        "winnerId": winner_id,
    }
