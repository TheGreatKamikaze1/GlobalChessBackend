from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from core.models import Game, GiftTransfer, User
from premium.service import get_membership_payload


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
    current_rating = int(getattr(user, "current_rating", 1200)) if user else 1200

    membership = get_membership_payload(db, user_id)

    sent_gifts = db.query(GiftTransfer).filter(GiftTransfer.sender_id == user_id).count()
    received_gifts = db.query(GiftTransfer).filter(GiftTransfer.recipient_id == user_id).count()
    redeemed_gifts = (
        db.query(GiftTransfer)
        .filter(GiftTransfer.recipient_id == user_id, GiftTransfer.status == "REDEEMED")
        .count()
    )

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
                "stake": 0.0,
                "completedAt": game.completed_at,
            }
        )

    return {
        "totalGames": int(total_games),
        "wins": int(wins),
        "losses": int(losses),
        "draws": int(draws),
        "winRate": float(win_rate),
        "currentBalance": 0.0,
        "totalEarnings": 0.0,
        "currentRating": int(current_rating),
        "isPremium": membership["isPremium"],
        "membershipTier": membership["membershipTier"],
        "giftActivity": {
            "sent": int(sent_gifts),
            "received": int(received_gifts),
            "redeemed": int(redeemed_gifts),
        },
        "recentGames": recent_games,
    }
