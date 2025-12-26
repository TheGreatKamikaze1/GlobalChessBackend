import chess
import json
from sqlalchemy.orm import Session
from core.models import Game, User

def process_move(db: Session, game_id: int, user_id: int, move_uci: str):
    # Lock the row to prevent "Double Move" exploits
    game = db.query(Game).filter(Game.id == game_id).with_for_update().first()
    
    if not game or game.status != "ONGOING":
        return {"error": "GAME_NOT_ACTIVE"}

    board = chess.Board(game.current_fen)
    
    # 1. Check whose turn it is
    is_white = (user_id == game.white_id)
    if (board.turn == chess.WHITE and not is_white) or (board.turn == chess.BLACK and is_white):
        return {"error": "NOT_YOUR_TURN"}

    # 2. Validate move legality
    try:
        move = chess.Move.from_uci(move_uci)
        if move not in board.legal_moves:
            return {"error": "ILLEGAL_MOVE"}
    except:
        return {"error": "INVALID_FORMAT"}

    # 3. Apply move and check for Game Over
    board.push(move)
    moves_list = json.loads(game.moves)
    moves_list.append(move_uci)
    
    game.current_fen = board.fen()
    game.moves = json.dumps(moves_list)

    if board.is_game_over():
        game.status = "COMPLETED"
        if board.is_checkmate():
            game.result = "WHITE_WIN" if is_white else "BLACK_WIN"
            # Update balances: Winner gets 2x stake (minus platform fee if any)
            winner = db.query(User).filter(User.id == user_id).first()
            winner.balance += (game.stake * 2)
        else:
            game.result = "DRAW"
            # Return stakes to both
            db.query(User).filter(User.id.in_([game.white_id, game.black_id])).update({
                User.balance: User.balance + game.stake
            }, synchronize_session=False)

    db.commit()
    return {"success": True, "fen": game.current_fen, "gameOver": board.is_game_over()}