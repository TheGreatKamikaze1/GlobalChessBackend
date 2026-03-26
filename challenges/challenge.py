from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import secrets
import chess

from core.database import get_db
from core.models import User, Challenge, Game
from core.ratings import determine_rating_category, get_user_rating, normalize_time_control
from challenges.challenge_schema import (
    CreateChallengeSchema,
    AvailableChallenge,
    ChallengeList,
    UserMini,
)
from game_management.dependencies import get_current_user_id_dep
from game_management.ratings import initialize_game_rating_snapshot

router = APIRouter(tags=["Challenges"])


def orm_user_mini(user: User, rating_category: str | None = None) -> dict:
    category = rating_category or "blitz"
    return {
        "id": str(user.id),
        "username": user.username,
        "displayName": user.display_name,
        "rating": get_user_rating(user, category),
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_challenge(
    req: CreateChallengeSchema,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stake = float(req.stake or 0)
    if stake > 0:
        raise HTTPException(
            status_code=400,
            detail="Staked challenges are no longer supported. Create a free match instead.",
        )

    now = datetime.now(timezone.utc)
<<<<<<< HEAD
    normalized_time_control = normalize_time_control(req.time_control)
    rating_category = determine_rating_category(normalized_time_control)
=======
>>>>>>> 89449e5a69ac70b3215a33ca65e8140c6c956118

    expires_at = now + timedelta(hours=1)

    challenge = Challenge(
        creator_id=user_id,
        stake=0,
        expires_at=expires_at,
        time_control=normalized_time_control,
        status="OPEN",
        color_preference=req.color,
        is_rated=req.rated,
    )

    db.add(challenge)
    db.commit()
    db.refresh(challenge)

    return {
        "success": True,
        "data": {
            "id": str(challenge.id),
            "creatorId": str(challenge.creator_id),
            "stake": 0.0,
            "timeControl": challenge.time_control,
            "isRated": bool(challenge.is_rated),
            "ratingCategory": rating_category,
            "status": challenge.status,
            "createdAt": challenge.created_at,
            "expiresAt": challenge.expires_at,
        },
    }


@router.get("/available", response_model=ChallengeList)
async def get_available_challenges(
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    now = datetime.now(timezone.utc)

    
    db.query(Challenge).filter(
        Challenge.status == "OPEN",
        Challenge.expires_at <= now,
    ).update({Challenge.status: "EXPIRED"}, synchronize_session=False)
    db.query(Challenge).filter(
        Challenge.status == "OPEN",
        Challenge.stake > 0,
    ).update({Challenge.status: "EXPIRED"}, synchronize_session=False)
    db.commit()

    base_query = db.query(Challenge).filter(
        Challenge.status == "OPEN",
        Challenge.expires_at > now,
        Challenge.stake <= 0,
    )

    total = base_query.count()
    challenges = (
        base_query.order_by(Challenge.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    data = [
        AvailableChallenge(
            id=str(c.id),
            creatorId=str(c.creator_id),
            stake=0.0,
            timeControl=c.time_control,
            isRated=bool(getattr(c, "is_rated", True)),
            ratingCategory=determine_rating_category(c.time_control),
            status=c.status,
            createdAt=c.created_at,
            expiresAt=c.expires_at,
            creator=UserMini(**orm_user_mini(c.creator, determine_rating_category(c.time_control))),
        )
        for c in challenges
    ]

    return {
        "success": True,
        "data": data,
        "pagination": {"total": total, "limit": limit, "offset": offset},
    }


@router.post("/{challenge_id}/accept")
async def accept_challenge(
    challenge_id: str,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db),
):
    try:
        challenge = (
            db.query(Challenge)
            .filter(Challenge.id == challenge_id)
            .with_for_update()
            .first()
        )
        if not challenge:
            raise HTTPException(status_code=404, detail="Challenge not found")

        now = datetime.now(timezone.utc)

        if challenge.status != "OPEN":
            raise HTTPException(status_code=400, detail="Challenge not available")

        if challenge.expires_at <= now:
            raise HTTPException(status_code=400, detail="Challenge expired")

       
        if str(challenge.creator_id) == str(user_id):
            raise HTTPException(status_code=400, detail="Cannot accept your own challenge")

        if float(challenge.stake or 0) > 0:
            challenge.status = "EXPIRED"
            db.commit()
            raise HTTPException(status_code=400, detail="Staked challenges are no longer supported")

        existing_game = db.query(Game).filter(Game.challenge_id == challenge.id).first()
        if existing_game:
            return {
                "success": True,
                "data": {
                    "challengeId": str(challenge.id),
                    "gameId": str(existing_game.id),
                    "message": "Challenge already accepted. Game already exists.",
                },
            }

        creator = (
            db.query(User)
            .filter(User.id == challenge.creator_id)
            .with_for_update()
            .first()
        )
        acceptor = db.query(User).filter(User.id == user_id).with_for_update().first()

        if not creator or not acceptor:
            raise HTTPException(status_code=404, detail="User not found")

        # COLOR ASSIGNMENT
        color_pref = getattr(challenge, "color_preference", "auto") or "auto"

        if color_pref == "white":
            white_id = challenge.creator_id
            black_id = user_id
        elif color_pref == "black":
            white_id = user_id
            black_id = challenge.creator_id
        else:
            if secrets.choice([True, False]):
                white_id = challenge.creator_id
                black_id = user_id
            else:
                white_id = user_id
                black_id = challenge.creator_id

        normalized_time_control = normalize_time_control(challenge.time_control)
        rating_category = determine_rating_category(normalized_time_control)
        white_player = creator if str(creator.id) == str(white_id) else acceptor
        black_player = creator if str(creator.id) == str(black_id) else acceptor

        new_game = Game(
            challenge_id=challenge.id,
            white_id=white_id,
            black_id=black_id,
            stake=0,
<<<<<<< HEAD
            time_control=normalized_time_control,
            rating_category=rating_category,
            is_rated=bool(getattr(challenge, "is_rated", True)),
=======
>>>>>>> 89449e5a69ac70b3215a33ca65e8140c6c956118
            status="ONGOING",
            current_fen=chess.STARTING_FEN,
            moves="[]",
            started_at=now,
        )

        initialize_game_rating_snapshot(new_game, white_player, black_player)

        challenge.status = "ACCEPTED"
        challenge.acceptor_id = user_id

        db.add(new_game)
        db.commit()
        db.refresh(new_game)

        return {
            "success": True,
            "data": {
                "challengeId": str(challenge.id),
                "gameId": str(new_game.id),
                "message": "Challenge accepted. Game started.",
            },
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
