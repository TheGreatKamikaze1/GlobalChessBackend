from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from core.models import Game
from core.models import User
import json

def get_dashboard_stats(db: Session, user_id: int):

    user_games_query = db.query(Game).filter(
        or_(Game.white_id == user_id, Game.black_id == user_id),
        Game.status == "COMPLETED"
    )
    
    total_games = user_games_query.count()
    
  
    wins = 0
    draws = 0
    if total_games > 0:
        all_games = user_games_query.all()
        for g in all_games:
            if g.result == "DRAW":
                draws += 1
            elif (g.result == "WHITE_WIN" and g.white_id == user_id) or \
                 (g.result == "BLACK_WIN" and g.black_id == user_id):
                wins += 1

    losses = total_games - wins - draws
    win_rate = round((wins / total_games) * 100, 1) if total_games > 0 else 0.0

    #  Fetch Balance 
    user = db.query(User).filter(User.id == user_id).first()
    current_balance = float(user.balance) if user else 0.0
    current_rating = getattr(user, 'rating', 1200) # Fallback if rating column missing

    
    recent_games_raw = user_games_query.order_by(Game.completed_at.desc()).limit(5).all()
    recent_games = []
    
    for game in recent_games_raw:
        # Determine if user was winner/loser
        is_win = (game.result == "WHITE_WIN" and game.white_id == user_id) or \
                 (game.result == "BLACK_WIN" and game.black_id == user_id)
        
        # Get opponent
        opponent = game.black if game.white_id == user_id else game.white
        
        recent_games.append({
            "id": str(game.id),
            "opponent": opponent.username if opponent else "Unknown",
            "result": "WIN" if is_win else ("DRAW" if game.result == "DRAW" else "LOSS"),
            "stake": float(game.stake),
            "completedAt": game.completed_at
        })

    return {
        "totalGames": total_games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "winRate": win_rate,
        "currentBalance": current_balance,
        "totalEarnings": 0.0, 
        "currentRating": current_rating,
        "recentGames": recent_games
    }