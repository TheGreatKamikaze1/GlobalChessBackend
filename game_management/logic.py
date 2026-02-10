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
    fen = (game.current_fen or "").strip()
    return fen if fen else chess.STARTING_FEN


def _try_apply_premove(game: Game, board: chess.Board) -> tuple[bool, str | None, str | None]:
   
    side_to_move = board.turn 

    premove = game.premove_white if side_to_move == chess.WHITE else game.premove_black
    if not premove:
        return (False, None, None)

    premove = premove.strip().lower()

    try:
        mv = chess.Move.from_uci(premove)

        if mv not in board.legal_moves:
            
            if side_to_move == chess.WHITE:
                game.premove_white = None
            else:
                game.premove_black = None
            return (False, None, None)

        san = board.san(mv)
        board.push(mv)

       
        if side_to_move == chess.WHITE:
            game.premove_white = None
        else:
            game.premove_black = None

        return (True, premove, san)

    except Exception:
        # invalid stored premove => clear it
        if side_to_move == chess.WHITE:
            game.premove_white = None
        else:
            game.premove_black = None
        return (False, None, None)


def _parse_move(board: chess.Board, move_text: str) -> tuple[chess.Move, str, str]:
    s = move_text.strip()

    # Try UCI first
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


def process_move(db: Session, game_id: str, user_id: str, move_text: str):
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

    moves_list = _load_moves(game)

    board.push(move)
    moves_list.append(uci)

    premove_applied = False
    premove_uci = None
    premove_san = None

  
    if not board.is_game_over():
        premove_applied, premove_uci, premove_san = _try_apply_premove(game, board)
        if premove_applied and premove_uci:
            moves_list.append(premove_uci)

  
    game.current_fen = board.fen()
    game.moves = json.dumps(moves_list)

    # recompute after premove
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
            "premoveApplied": premove_applied,
            "premoveUci": premove_uci,
            "premoveSan": premove_san,
        }

    # GAME OVER HANDLING
    game.status = "COMPLETED"
    game.completed_at = datetime.now(timezone.utc)

    stake = float(game.stake or 0)
    winner_id = None

    if is_checkmate:
       
        if board.turn == chess.WHITE:
            winner_id = game.black_id
            game.result = "BLACK_WIN"
        else:
            winner_id = game.white_id
            game.result = "WHITE_WIN"

        game.winner_id = winner_id

        
        if stake > 0 and winner_id:
            winner = db.query(User).filter(User.id == winner_id).with_for_update().first()
            if winner:
                winner.balance += (game.stake * 2)
    else:
        game.result = "DRAW"
        if stake > 0:
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
        "premoveApplied": premove_applied,
        "premoveUci": premove_uci,
        "premoveSan": premove_san,
    }
