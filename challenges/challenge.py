from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import random

from core.database import get_db
from core.models import User, Challenge, Game
from challenges.challenge_schema import (
    CreateChallengeSchema,
    AvailableChallenge,
    ChallengeList,
)
from game_management.dependencies import get_current_user_id

router = APIRouter(tags=["Challenges"])


def orm_user_mini(user: User):
    return {
        "id": user.id,
        "username": user.username,
        "displayName": user.display_name,
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_challenge(
    req: CreateChallengeSchema,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).with_for_update().first()

    if not user or user.balance < req.stake:
        raise HTTPException(
            status_code=400,
            detail={"code": "INSUFFICIENT_BALANCE", "message": "Insufficient balance"},
        )

    # Make expires_at timezone-aware
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    challenge = Challenge(
        creator_id=user_id,
        stake=req.stake,
        expires_at=expires_at,
        time_control=req.time_control,
        status="OPEN",
        color_preference=getattr(req, "color", "auto"),  # default to "auto" if not provided
    )

    db.add(challenge)
    db.commit()
    db.refresh(challenge)

    return {
        "success": True,
        "data": {
            "id": challenge.id,
            "creatorId": challenge.creator_id,
            "stake": challenge.stake,
            "timeControl": challenge.time_control,
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

    base_query = db.query(Challenge).filter(
        Challenge.status == "OPEN",
        Challenge.expires_at > now,
    )

    total = base_query.count()
    challenges = base_query.offset(offset).limit(limit).all()

    data = [
        AvailableChallenge(
            id=c.id,
            creatorId=c.creator_id,
            stake=c.stake,
            timeControl=c.time_control,
            status=c.status,
            createdAt=c.created_at,
            expiresAt=c.expires_at,
            creator=orm_user_mini(c.creator),
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
    challenge_id: int,
    user_id: int = Depends(get_current_user_id),
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

        if challenge.creator_id == user_id:
            raise HTTPException(status_code=400, detail="Cannot accept your own challenge")

        creator = db.query(User).filter(User.id == challenge.creator_id).with_for_update().first()
        acceptor = db.query(User).filter(User.id == user_id).with_for_update().first()

        if creator.balance < challenge.stake or acceptor.balance < challenge.stake:
            raise HTTPException(status_code=400, detail="Insufficient balance")

        # ESCROW
        creator.balance -= challenge.stake
        acceptor.balance -= challenge.stake

        # COLOR ASSIGNMENT
        color_pref = getattr(challenge, "color_preference", "auto")
        if color_pref == "white":
            white_id = challenge.creator_id
            black_id = user_id
        elif color_pref == "black":
            white_id = user_id
            black_id = challenge.creator_id
        else:  # auto = random
            if random.choice([True, False]):
                white_id = challenge.creator_id
                black_id = user_id
            else:
                white_id = user_id
                black_id = challenge.creator_id

        new_game = Game(
            challenge_id=challenge.id,
            white_id=white_id,
            black_id=black_id,
            stake=challenge.stake,
            status="ONGOING",
            current_fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        )

        challenge.status = "ACCEPTED"
        challenge.acceptor_id = user_id

        db.add(new_game)
        db.commit()
        db.refresh(new_game)

        return {
            "success": True,
            "data": {
                "challengeId": challenge.id,
                "gameId": new_game.id,
                "message": "Challenge accepted. Game started.",
            },
        }

    except Exception:
        db.rollback()
        raise
