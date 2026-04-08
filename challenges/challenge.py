from datetime import datetime, timedelta, timezone

import chess
import secrets
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from challenges.challenge_schema import (
    AvailableChallenge,
    ChallengeList,
    CreateChallengeSchema,
    MatchmakeResponse,
    UserMini,
)
from core.database import get_db
from core.economy import (
    create_transaction_record,
    debit_user_balance,
    ensure_sufficient_balance,
    money_to_float,
    to_money,
)
from core.models import Challenge, Game, User
from core.ratings import determine_rating_category, get_user_rating, normalize_time_control
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


def _challenge_payload(challenge: Challenge) -> dict:
    normalized_time_control = normalize_time_control(challenge.time_control)
    rating_category = determine_rating_category(normalized_time_control)

    return {
        "id": str(challenge.id),
        "creatorId": str(challenge.creator_id),
        "stake": money_to_float(challenge.stake),
        "timeControl": normalized_time_control,
        "isRated": bool(getattr(challenge, "is_rated", True)),
        "ratingCategory": rating_category,
        "status": challenge.status,
        "createdAt": challenge.created_at,
        "expiresAt": challenge.expires_at,
    }


def _refund_expired_challenge(db: Session, challenge: Challenge) -> None:
    stake = to_money(challenge.stake)
    if stake > 0:
        creator = db.query(User).filter(User.id == challenge.creator_id).with_for_update().first()
        if creator:
            creator.balance = to_money(creator.balance) + stake
            create_transaction_record(
                db,
                user_id=str(creator.id),
                amount=stake,
                type="STAKE_REFUND",
                reference=f"stake_refund_expired_{challenge.id}",
                meta={
                    "reason": "CHALLENGE_EXPIRED",
                    "challengeId": str(challenge.id),
                },
            )

    challenge.status = "EXPIRED"


def _cleanup_open_challenges(db: Session, now: datetime) -> None:
    expired_challenges = (
        db.query(Challenge)
        .filter(
            Challenge.status == "OPEN",
            Challenge.expires_at <= now,
        )
        .with_for_update(skip_locked=True)
        .all()
    )

    if not expired_challenges:
        return

    for challenge in expired_challenges:
        _refund_expired_challenge(db, challenge)

    db.commit()


def _resolve_colors(
    creator_id: str,
    acceptor_id: str,
    creator_pref: str | None,
    acceptor_pref: str | None = "auto",
) -> tuple[str, str]:
    creator_pref = (creator_pref or "auto").lower()
    acceptor_pref = (acceptor_pref or "auto").lower()

    if creator_pref == "white":
        if acceptor_pref == "white":
            raise HTTPException(status_code=409, detail="Color preferences conflict")
        return str(creator_id), str(acceptor_id)

    if creator_pref == "black":
        if acceptor_pref == "black":
            raise HTTPException(status_code=409, detail="Color preferences conflict")
        return str(acceptor_id), str(creator_id)

    if acceptor_pref == "white":
        return str(acceptor_id), str(creator_id)

    if acceptor_pref == "black":
        return str(creator_id), str(acceptor_id)

    if secrets.choice([True, False]):
        return str(creator_id), str(acceptor_id)

    return str(acceptor_id), str(creator_id)


def _reserve_creator_stake_for_challenge(db: Session, user: User, challenge: Challenge) -> None:
    stake = to_money(challenge.stake)
    if stake <= 0:
        return

    debit_user_balance(user, stake)
    create_transaction_record(
        db,
        user_id=str(user.id),
        amount=stake,
        type="STAKE_HOLD",
        reference=f"stake_hold_challenge_{challenge.id}",
        meta={
            "challengeId": str(challenge.id),
            "role": "creator",
        },
    )


def _collect_acceptor_stake(db: Session, acceptor: User, challenge: Challenge) -> None:
    stake = to_money(challenge.stake)
    if stake <= 0:
        return

    ensure_sufficient_balance(
        acceptor,
        stake,
        detail="Insufficient wallet balance for this stake table",
    )
    debit_user_balance(acceptor, stake)
    create_transaction_record(
        db,
        user_id=str(acceptor.id),
        amount=stake,
        type="STAKE_HOLD",
        reference=f"stake_hold_accept_{challenge.id}_{acceptor.id}",
        meta={
            "challengeId": str(challenge.id),
            "role": "acceptor",
        },
    )


def _start_game_from_challenge(
    db: Session,
    challenge: Challenge,
    acceptor_id: str,
    now: datetime,
    acceptor_color: str = "auto",
) -> tuple[Game, str]:
    if challenge.status != "OPEN":
        raise HTTPException(status_code=400, detail="Challenge not available")

    if challenge.expires_at <= now:
        _refund_expired_challenge(db, challenge)
        db.commit()
        raise HTTPException(status_code=400, detail="Challenge expired")

    if str(challenge.creator_id) == str(acceptor_id):
        raise HTTPException(status_code=400, detail="Cannot accept your own challenge")

    existing_game = db.query(Game).filter(Game.challenge_id == challenge.id).first()
    if existing_game:
        return existing_game, "Challenge already accepted. Game already exists."

    creator = (
        db.query(User)
        .filter(User.id == challenge.creator_id)
        .with_for_update()
        .first()
    )
    acceptor = db.query(User).filter(User.id == acceptor_id).with_for_update().first()

    if not creator or not acceptor:
        raise HTTPException(status_code=404, detail="User not found")

    _collect_acceptor_stake(db, acceptor, challenge)

    white_id, black_id = _resolve_colors(
        creator_id=str(challenge.creator_id),
        acceptor_id=str(acceptor_id),
        creator_pref=getattr(challenge, "color_preference", "auto"),
        acceptor_pref=acceptor_color,
    )

    normalized_time_control = normalize_time_control(challenge.time_control)
    rating_category = determine_rating_category(normalized_time_control)
    white_player = creator if str(creator.id) == str(white_id) else acceptor
    black_player = creator if str(creator.id) == str(black_id) else acceptor

    new_game = Game(
        challenge_id=challenge.id,
        white_id=white_id,
        black_id=black_id,
        stake=to_money(challenge.stake),
        time_control=normalized_time_control,
        rating_category=rating_category,
        is_rated=bool(getattr(challenge, "is_rated", True)),
        status="ONGOING",
        current_fen=chess.STARTING_FEN,
        moves="[]",
        started_at=now,
    )

    initialize_game_rating_snapshot(new_game, white_player, black_player)

    challenge.status = "ACCEPTED"
    challenge.acceptor_id = acceptor_id

    db.add(new_game)
    db.commit()
    db.refresh(new_game)

    return new_game, "Challenge accepted. Game started."


def _get_existing_open_challenge(
    db: Session,
    *,
    user_id: str,
    stake: float,
    normalized_time_control: str,
    rated: bool,
    color: str,
    now: datetime,
) -> Challenge | None:
    return (
        db.query(Challenge)
        .filter(
            Challenge.creator_id == user_id,
            Challenge.status == "OPEN",
            Challenge.time_control == normalized_time_control,
            Challenge.is_rated == rated,
            Challenge.color_preference == color,
            Challenge.expires_at > now,
            Challenge.stake == to_money(stake),
        )
        .order_by(Challenge.created_at.desc())
        .with_for_update(skip_locked=True)
        .first()
    )


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_challenge(
    req: CreateChallengeSchema,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc)
    normalized_time_control = normalize_time_control(req.time_control)
    expires_at = now + timedelta(hours=1)
    stake = to_money(req.stake)

    if stake > 0:
        ensure_sufficient_balance(
            user,
            stake,
            detail="Insufficient wallet balance for this stake table",
        )

    challenge = Challenge(
        creator_id=user_id,
        stake=stake,
        expires_at=expires_at,
        time_control=normalized_time_control,
        status="OPEN",
        color_preference=req.color,
        is_rated=req.rated,
    )

    db.add(challenge)
    db.flush()

    _reserve_creator_stake_for_challenge(db, user, challenge)

    db.commit()
    db.refresh(challenge)

    return {
        "success": True,
        "data": _challenge_payload(challenge),
    }


@router.get("/available", response_model=ChallengeList)
async def get_available_challenges(
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    now = datetime.now(timezone.utc)
    _cleanup_open_challenges(db, now)

    base_query = db.query(Challenge).filter(
        Challenge.status == "OPEN",
        Challenge.expires_at > now,
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
            stake=money_to_float(c.stake),
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

        game, message = _start_game_from_challenge(
            db=db,
            challenge=challenge,
            acceptor_id=user_id,
            now=now,
        )

        return {
            "success": True,
            "data": {
                "challengeId": str(challenge.id),
                "gameId": str(game.id),
                "message": message,
            },
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.post("/matchmake", response_model=MatchmakeResponse)
async def matchmake(
    req: CreateChallengeSchema,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc)
    normalized_time_control = normalize_time_control(req.time_control)
    rating_category = determine_rating_category(normalized_time_control)
    stake = to_money(req.stake)

    _cleanup_open_challenges(db, now)

    try:
        existing_challenge = _get_existing_open_challenge(
            db,
            user_id=user_id,
            stake=money_to_float(stake),
            normalized_time_control=normalized_time_control,
            rated=req.rated,
            color=req.color,
            now=now,
        )

        if existing_challenge:
            return {
                "success": True,
                "data": {
                    "matched": False,
                    "status": "QUEUED",
                    "challengeId": str(existing_challenge.id),
                    "gameId": None,
                    "message": "Waiting for an opponent.",
                    "stake": money_to_float(existing_challenge.stake),
                    "createdAt": existing_challenge.created_at,
                    "expiresAt": existing_challenge.expires_at,
                    "timeControl": normalized_time_control,
                    "isRated": bool(req.rated),
                    "ratingCategory": rating_category,
                },
            }

        if stake > 0:
            ensure_sufficient_balance(
                user,
                stake,
                detail="Insufficient wallet balance for this stake table",
            )

        candidate_challenges = (
            db.query(Challenge)
            .filter(
                Challenge.status == "OPEN",
                Challenge.creator_id != user_id,
                Challenge.time_control == normalized_time_control,
                Challenge.is_rated == req.rated,
                Challenge.expires_at > now,
                Challenge.stake == stake,
            )
            .order_by(Challenge.created_at.asc())
            .with_for_update(skip_locked=True)
            .all()
        )

        for challenge in candidate_challenges:
            try:
                game, message = _start_game_from_challenge(
                    db=db,
                    challenge=challenge,
                    acceptor_id=user_id,
                    now=now,
                    acceptor_color=req.color,
                )
                return {
                    "success": True,
                    "data": {
                        "matched": True,
                        "status": "MATCHED",
                        "challengeId": str(challenge.id),
                        "gameId": str(game.id),
                        "message": message,
                        "stake": money_to_float(challenge.stake),
                        "createdAt": challenge.created_at,
                        "expiresAt": challenge.expires_at,
                        "timeControl": normalized_time_control,
                        "isRated": bool(req.rated),
                        "ratingCategory": rating_category,
                    },
                }
            except HTTPException as exc:
                if exc.status_code == 409:
                    db.rollback()
                    continue
                raise

        expires_at = now + timedelta(hours=1)
        new_challenge = Challenge(
            creator_id=user_id,
            stake=stake,
            expires_at=expires_at,
            time_control=normalized_time_control,
            status="OPEN",
            color_preference=req.color,
            is_rated=req.rated,
        )
        db.add(new_challenge)
        db.flush()

        _reserve_creator_stake_for_challenge(db, user, new_challenge)

        db.commit()
        db.refresh(new_challenge)

        return {
            "success": True,
            "data": {
                "matched": False,
                "status": "QUEUED",
                "challengeId": str(new_challenge.id),
                "gameId": None,
                "message": "Waiting for an opponent.",
                "stake": money_to_float(new_challenge.stake),
                "createdAt": new_challenge.created_at,
                "expiresAt": new_challenge.expires_at,
                "timeControl": normalized_time_control,
                "isRated": bool(req.rated),
                "ratingCategory": rating_category,
            },
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
