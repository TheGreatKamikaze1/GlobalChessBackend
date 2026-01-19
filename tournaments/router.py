from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, timedelta, timezone
import random

from core.database import get_db
from core.models import User, Transaction
from core.auth import get_current_user

from tournaments.models import Tournament, TournamentParticipant, TournamentMatch
from tournaments.schemas import (
    TournamentCreate,
    TournamentResponse,
    JoinTournamentResponse,
    FinishTournamentPayload,
    TournamentDetailsResponse,
)

from tournaments.service import schedule_tournament

router = APIRouter(tags=["Tournaments"])


def _maybe_update_status(db: Session, tournament: Tournament) -> Tournament:
    """
    Ensures tournament.status matches time:
    UPCOMING -> RUNNING at start_time
    RUNNING/UPCOMING -> FINISHED at end_time
    CANCELLED stays CANCELLED
    FINISHED stays FINISHED
    """
    if not tournament:
        return tournament

    if tournament.status in ("CANCELLED", "FINISHED"):
        return tournament

    now = datetime.now(timezone.utc)

   #guard it
    start_time = tournament.start_time
    if start_time is not None and start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)

    end_time = None
    if start_time is not None:
        end_time = start_time + timedelta(minutes=int(tournament.duration_minutes or 0))

    changed = False

    if start_time and now >= start_time and tournament.status == "UPCOMING":
        tournament.status = "RUNNING"
        changed = True

    if end_time and now >= end_time and tournament.status in ("UPCOMING", "RUNNING"):
        tournament.status = "FINISHED"
        tournament.escrow_balance = Decimal("0.00")
        changed = True

    if changed:
        db.commit()
        db.refresh(tournament)

    return tournament



# Create tournament

@router.post("/", response_model=TournamentResponse)
def create_tournament(
    payload: TournamentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.deposit_required and payload.entry_fee > current_user.balance:
        raise HTTPException(400, "Insufficient balance")

    tournament = Tournament(
        creator_id=current_user.id,
        name=payload.name,
        description=payload.description,
        entry_fee=payload.entry_fee,
        deposit_required=payload.deposit_required,
        prize_rules=payload.prize_rules.dict(),
        max_players=payload.max_players,
        format=payload.format,
        rounds=payload.rounds,
        time_control=payload.time_control,
        start_time=payload.start_time,
        duration_minutes=payload.duration_minutes,
        escrow_balance=Decimal(payload.entry_fee if payload.deposit_required else 0),
    )

    if payload.deposit_required:
        current_user.balance -= Decimal(payload.entry_fee)
        db.add(
            Transaction(
                user_id=current_user.id,
                amount=payload.entry_fee,
                type="TOURNAMENT_CREATE",
                status="COMPLETED",
            )
        )

    db.add(tournament)
    db.commit()
    db.refresh(tournament)

    # Schedule start/finish (best effort)
    schedule_tournament(
        tournament_id=tournament.id,
        start_time=payload.start_time,
        duration_minutes=payload.duration_minutes,
    )

    return tournament



# Join tournament

@router.post("/{tournament_id}/join", response_model=JoinTournamentResponse)
def join_tournament(
    tournament_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tournament = db.query(Tournament).filter_by(id=tournament_id).first()
    if not tournament:
        raise HTTPException(404, "Tournament not found")

    tournament = _maybe_update_status(db, tournament)

    if tournament.status != "UPCOMING":
        raise HTTPException(400, "Tournament already started")

    # max players check
    current_count = (
        db.query(TournamentParticipant)
        .filter_by(tournament_id=tournament.id)
        .count()
    )
    if current_count >= int(tournament.max_players or 0):
        raise HTTPException(400, "Tournament is full")

    participant = (
        db.query(TournamentParticipant)
        .filter_by(tournament_id=tournament.id, user_id=current_user.id)
        .first()
    )
    if participant:
        raise HTTPException(400, "Already joined")

    paid = False
    if tournament.deposit_required:
        if current_user.balance < tournament.entry_fee:
            raise HTTPException(400, "Insufficient balance")
        current_user.balance -= Decimal(tournament.entry_fee)
        tournament.escrow_balance += Decimal(tournament.entry_fee)
        paid = True
        db.add(
            Transaction(
                user_id=current_user.id,
                amount=tournament.entry_fee,
                type="TOURNAMENT_JOIN",
                status="COMPLETED",
            )
        )

    participant = TournamentParticipant(
        tournament_id=tournament.id, user_id=current_user.id, paid=paid
    )

    db.add(participant)
    db.commit()
    return JoinTournamentResponse(tournament_id=tournament.id, user_id=current_user.id, paid=paid)



# Cancel tournament

@router.post("/{tournament_id}/cancel")
def cancel_tournament(
    tournament_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tournament = db.query(Tournament).filter_by(id=tournament_id).first()
    if not tournament or tournament.creator_id != current_user.id:
        raise HTTPException(403)

    tournament = _maybe_update_status(db, tournament)

    if tournament.status != "UPCOMING":
        raise HTTPException(400, "Cannot cancel running tournament")

    participants = (
        db.query(TournamentParticipant).filter_by(tournament_id=tournament.id).all()
    )

    refund_amount = tournament.entry_fee
    for p in participants:
        user = db.query(User).filter_by(id=p.user_id).first()
        if p.paid and user:
            user.balance += Decimal(refund_amount)
            db.add(
                Transaction(
                    user_id=user.id,
                    amount=refund_amount,
                    type="TOURNAMENT_REFUND",
                    status="COMPLETED",
                )
            )

    # refund creator (create deposit)
    if tournament.deposit_required and tournament.entry_fee > 0:
        creator = db.query(User).filter_by(id=tournament.creator_id).first()
        if creator:
            creator.balance += Decimal(tournament.entry_fee)
            db.add(
                Transaction(
                    user_id=creator.id,
                    amount=tournament.entry_fee,
                    type="TOURNAMENT_REFUND",
                    status="COMPLETED",
                )
            )

    tournament.status = "CANCELLED"
    tournament.escrow_balance = Decimal("0.00")
    db.commit()
    return {"status": "cancelled"}



# Manual finish 

@router.post("/{tournament_id}/finish")
def finish_tournament(
    tournament_id: str,
    payload: FinishTournamentPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tournament = db.query(Tournament).filter_by(id=tournament_id).first()
    if not tournament or tournament.creator_id != current_user.id:
        raise HTTPException(403)

    tournament = _maybe_update_status(db, tournament)

    if tournament.status not in ("RUNNING", "UPCOMING"):
        raise HTTPException(400, "Tournament not running")

    rules = tournament.prize_rules
    total = Decimal(str(tournament.escrow_balance or 0))

    for idx, place in enumerate(rules["places"]):
        user_id = payload.results[place - 1]
        share = Decimal(str(rules["distribution"][idx]))
        amount = (total * share).quantize(Decimal("0.01"))

        user = db.query(User).filter_by(id=user_id).first()
        if user:
            user.balance += amount
            db.add(
                Transaction(
                    user_id=user_id,
                    amount=amount,
                    type="TOURNAMENT_WIN",
                    status="COMPLETED",
                )
            )

    tournament.status = "FINISHED"
    tournament.escrow_balance = Decimal("0.00")
    db.commit()
    return {"status": "completed"}



# List tournaments

@router.get("/list")
def list_tournaments(
    status: str = Query("ALL", description="Filter by status: UPCOMING, RUNNING, FINISHED, CANCELLED"),
    db: Session = Depends(get_db),
):
    query = db.query(Tournament)

    if status != "ALL":
        query = query.filter(Tournament.status == status.upper())

    tournaments = query.order_by(Tournament.start_time.desc()).all()

    #  status refresh
    for t in tournaments:
        _maybe_update_status(db, t)

    return {
        "success": True,
        "data": [
            {
                "id": t.id,
                "name": t.name,
                "creator_id": t.creator_id,
                "start_time": t.start_time,
                "duration_minutes": float(t.duration_minutes),
                "time_control": t.time_control,
                "deposit_required": t.deposit_required,
                "entry_fee": float(t.entry_fee),
                "prize_rules": t.prize_rules,
                "status": (t.status or "").lower(),
                "escrow_balance": float(t.escrow_balance),
                "created_at": t.created_at,
                "max_players": int(t.max_players or 0),
                "format": t.format,
                "rounds": int(t.rounds or 0),
            }
            for t in tournaments
        ],
        "count": len(tournaments),
    }


# Get tournament by id

@router.get("/{tournament_id}", response_model=TournamentDetailsResponse)
def get_tournament_by_id(
    tournament_id: str,
    db: Session = Depends(get_db),
):
    tournament = db.query(Tournament).filter_by(id=tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    tournament = _maybe_update_status(db, tournament)

    participants_rows = (
        db.query(TournamentParticipant, User)
        .join(User, User.id == TournamentParticipant.user_id)
        .filter(TournamentParticipant.tournament_id == tournament_id)
        .all()
    )

    players_count = len(participants_rows)

    matches_rows = (
        db.query(TournamentMatch)
        .filter_by(tournament_id=tournament_id)
        .order_by(TournamentMatch.round.asc())
        .all()
    )

    wins = {user.id: 0 for _, user in participants_rows}
    losses = {user.id: 0 for _, user in participants_rows}
    user_map = {user.id: user.username for _, user in participants_rows}

    for m in matches_rows:
        if m.status != "completed" or not m.result:
            continue
        if m.result == "1-0":
            wins[m.white_id] = wins.get(m.white_id, 0) + 1
            losses[m.black_id] = losses.get(m.black_id, 0) + 1
        elif m.result == "0-1":
            wins[m.black_id] = wins.get(m.black_id, 0) + 1
            losses[m.white_id] = losses.get(m.white_id, 0) + 1

    prize_pool = float(tournament.escrow_balance or 0)
    prizes = []
    rules = tournament.prize_rules or {}
    places = rules.get("places", [])
    dist = rules.get("distribution", [])

    def _place_label(n: int) -> str:
        if n == 1:
            return "1st"
        if n == 2:
            return "2nd"
        if n == 3:
            return "3rd"
        return f"{n}th"

    for idx, place in enumerate(places):
        if idx >= len(dist):
            break
        share = float(dist[idx] or 0)
        prizes.append({"place": _place_label(place), "amount": prize_pool * share})

    participants_out = []
    for p, user in participants_rows:
        participants_out.append(
            {
                "id": user.id,
                "username": user.username,
                "wins": wins.get(user.id, 0),
                "losses": losses.get(user.id, 0),
                "score": float(p.score or 0),
                "paid": bool(p.paid),
            }
        )

    matches_out = []
    for m in matches_rows:
        matches_out.append(
            {
                "id": m.id,
                "round": m.round,
                "white_id": m.white_id,
                "black_id": m.black_id,
                "white": user_map.get(m.white_id, m.white_id),
                "black": user_map.get(m.black_id, m.black_id),
                "status": m.status,
                "result": m.result,
            }
        )

    return {
        "id": tournament.id,
        "creator_id": tournament.creator_id,
        "name": tournament.name,
        "description": tournament.description,
        "status": (tournament.status or "").lower(),
        "players": players_count,
        "max_players": int(tournament.max_players),
        "prizePool": prize_pool,
        "entryFee": float(tournament.entry_fee or 0),
        "startDate": tournament.start_time,
        "timeControl": tournament.time_control,
        "format": tournament.format,
        "rounds": int(tournament.rounds),
        "duration_minutes": int(tournament.duration_minutes),
        "prize_rules": tournament.prize_rules,
        "prizes": prizes,
        "participants": participants_out,
        "matches": matches_out,
    }



# Get all participants

@router.get("/{tournament_id}/participants")
def get_tournament_participants(
    tournament_id: str,
    db: Session = Depends(get_db),
):
    tournament = db.query(Tournament).filter_by(id=tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    tournament = _maybe_update_status(db, tournament)

    participants = (
        db.query(TournamentParticipant, User)
        .join(User, User.id == TournamentParticipant.user_id)
        .filter(TournamentParticipant.tournament_id == tournament_id)
        .all()
    )

    return {
        "success": True,
        "tournament_id": tournament_id,
        "count": len(participants),
        "participants": [
            {
                "user_id": user.id,
                "username": user.username,
                "joined_at": p.joined_at,
                "score": float(p.score or 0),
                "paid": p.paid,
            }
            for p, user in participants
        ],
    }



# Pairings / Swiss-ish

@router.post("/{tournament_id}/pairings/{round_no}")
def create_round_pairings(
    tournament_id: str,
    round_no: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tournament = db.query(Tournament).filter_by(id=tournament_id).first()
    if not tournament:
        raise HTTPException(404, "Tournament not found")

    tournament = _maybe_update_status(db, tournament)

    if tournament.creator_id != current_user.id:
        raise HTTPException(403, "Only creator can generate pairings")

    if round_no < 1 or round_no > int(tournament.rounds or 0):
        raise HTTPException(400, "Invalid round number")

    existing = (
        db.query(TournamentMatch)
        .filter_by(tournament_id=tournament_id, round=round_no)
        .first()
    )
    if existing:
        raise HTTPException(400, "Pairings for this round already exist")

    pairings = generate_pairings(db, tournament_id, round_no)

    for white_id, black_id in pairings:
        db.add(
            TournamentMatch(
                tournament_id=tournament_id,
                round=round_no,
                white_id=white_id,
                black_id=black_id,
                status="scheduled",
            )
        )

    db.commit()
    return {"success": True, "round": round_no, "created_matches": len(pairings)}


@router.post("/{tournament_id}/matches/{match_id}/result")
def submit_match_result(
    tournament_id: str,
    match_id: str,
    result: str = Query(..., description="1-0, 0-1, 1/2-1/2"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tournament = db.query(Tournament).filter_by(id=tournament_id).first()
    if not tournament:
        raise HTTPException(404, "Tournament not found")

    match = (
        db.query(TournamentMatch)
        .filter_by(id=match_id, tournament_id=tournament_id)
        .first()
    )
    if not match:
        raise HTTPException(404, "Match not found")

    if result not in ("1-0", "0-1", "1/2-1/2"):
        raise HTTPException(400, "Invalid result")

    match.result = result
    match.status = "completed"

    white_p = (
        db.query(TournamentParticipant)
        .filter_by(tournament_id=tournament_id, user_id=match.white_id)
        .first()
    )
    black_p = (
        db.query(TournamentParticipant)
        .filter_by(tournament_id=tournament_id, user_id=match.black_id)
        .first()
    )

    if not white_p or not black_p:
        raise HTTPException(400, "Participants not found for this match")

    white_score = Decimal(str(white_p.score or 0))
    black_score = Decimal(str(black_p.score or 0))

    if result == "1-0":
        white_p.score = white_score + Decimal("1.0")
    elif result == "0-1":
        black_p.score = black_score + Decimal("1.0")
    else:
        white_p.score = white_score + Decimal("0.5")
        black_p.score = black_score + Decimal("0.5")

    db.commit()
    return {"success": True, "match_id": match.id, "result": match.result}


def _already_played(pairs_set: set[tuple[str, str]], a: str, b: str) -> bool:
    x, y = (a, b) if a < b else (b, a)
    return (x, y) in pairs_set


def _add_pair(pairs_set: set[tuple[str, str]], a: str, b: str):
    x, y = (a, b) if a < b else (b, a)
    pairs_set.add((x, y))


def generate_pairings(db: Session, tournament_id: str, round_no: int) -> list[tuple[str, str]]:
    participants = db.query(TournamentParticipant).filter_by(tournament_id=tournament_id).all()
    user_ids = [p.user_id for p in participants]

    prev_matches = db.query(TournamentMatch).filter_by(tournament_id=tournament_id).all()
    played = set()
    for m in prev_matches:
        _add_pair(played, m.white_id, m.black_id)

    if round_no == 1:
        random.shuffle(user_ids)
    else:
        score_map = {p.user_id: float(p.score or 0) for p in participants}
        user_ids.sort(key=lambda uid: score_map.get(uid, 0), reverse=True)

    pairings = []
    used = set()

    for i in range(len(user_ids)):
        a = user_ids[i]
        if a in used:
            continue

        opponent = None
        for j in range(i + 1, len(user_ids)):
            b = user_ids[j]
            if b in used:
                continue
            if not _already_played(played, a, b):
                opponent = b
                break

        if opponent is None:
            for j in range(i + 1, len(user_ids)):
                b = user_ids[j]
                if b not in used:
                    opponent = b
                    break

        if opponent is None:
            used.add(a)
            continue

        used.add(a)
        used.add(opponent)
        _add_pair(played, a, opponent)
        pairings.append((a, opponent))

    return pairings
