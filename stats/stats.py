from sqlalchemy.orm import Session
from sqlalchemy import or_, func, case
from core.models import Game, User


def get_dashboard_stats(db: Session, user_id: str):
    base = db.query(Game).filter(
        or_(Game.white_id == user_id, Game.black_id == user_id),
        Game.status == "COMPLETED",
    )

    total_games = base.count()

    wins = (
        db.query(func.count(Game.id))
        .filter(
            or_(Game.white_id == user_id, Game.black_id == user_id),
            Game.status == "COMPLETED",
            or_(
                (Game.result == "WHITE_WIN") & (Game.white_id == user_id),
                (Game.result == "BLACK_WIN") & (Game.black_id == user_id),
            ),
        )
        .scalar()
        or 0
    )

    draws = (
        db.query(func.count(Game.id))
        .filter(
            or_(Game.white_id == user_id, Game.black_id == user_id),
            Game.status == "COMPLETED",
            Game.result == "DRAW",
        )
        .scalar()
        or 0
    )

    losses = int(total_games) - int(wins) - int(draws)
    win_rate = round((wins / total_games) * 100, 1) if total_games > 0 else 0.0

    user = db.query(User).filter(User.id == user_id).first()
    current_balance = float(user.balance) if user else 0.0
    current_rating = int(getattr(user, "current_rating", 1200)) if user else 1200


    profit_query = (
        db.query(
            func.coalesce(
                func.sum(
                    case(
                        (Game.result == "DRAW", 0.0),
                        ((Game.result == "WHITE_WIN") & (Game.white_id == user_id), Game.stake),
                        ((Game.result == "BLACK_WIN") & (Game.black_id == user_id), Game.stake),
                        else_=-Game.stake,
                    )
                ),
                0.0,
            )
        )
        .filter(
            or_(Game.white_id == user_id, Game.black_id == user_id),
            Game.status == "COMPLETED",
        )
    )
    total_earnings = float(profit_query.scalar() or 0.0)

    recent_games_raw = base.order_by(Game.completed_at.desc()).limit(5).all()
    recent_games = []

    for game in recent_games_raw:
        is_win = (
            (game.result == "WHITE_WIN" and game.white_id == user_id)
            or (game.result == "BLACK_WIN" and game.black_id == user_id)
        )
        opponent = game.black if game.white_id == user_id else game.white

        recent_games.append(
            {
                "id": str(game.id),
                "opponent": opponent.username if opponent else "Unknown",
                "result": "WIN" if is_win else ("DRAW" if game.result == "DRAW" else "LOSS"),
                "stake": float(game.stake),
                "completedAt": game.completed_at,
            }
        )

    return {
        "totalGames": int(total_games),
        "wins": int(wins),
        "losses": int(losses),
        "draws": int(draws),
        "winRate": float(win_rate),
        "currentBalance": float(current_balance),
        "totalEarnings": float(total_earnings),
        "currentRating": int(current_rating),
        "recentGames": recent_games,
    }
