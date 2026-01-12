from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal
from typing import List

from core.database import get_db
from core.models import User, Transaction
from core.auth import get_current_user

from tournaments.models import Tournament, TournamentParticipant
from tournaments.schemas import TournamentCreate, TournamentResponse, JoinTournamentResponse, FinishTournamentPayload

from tournaments.service import schedule_tournament
from datetime import timedelta
from tournaments.tasks import start_tournament_task, finish_tournament_task
from fastapi import Query



router = APIRouter( tags=["Tournaments"])

#create
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
        time_control=payload.time_control,
        start_time=payload.start_time,
        duration_minutes=payload.duration_minutes,
        escrow_balance=Decimal(payload.entry_fee if payload.deposit_required else 0)
    )

    if payload.deposit_required:
        current_user.balance -= Decimal(payload.entry_fee)
        db.add(Transaction(
            user_id=current_user.id,
            amount=payload.entry_fee,
            type="TOURNAMENT_CREATE",
            status="COMPLETED",
        ))

    db.add(tournament)
    db.commit()
   
#     start_tournament_task.apply_async(
#     args=[tournament.id],
#     eta=payload.start_time
# )

#     end_time = payload.start_time + timedelta(minutes=payload.duration_minutes)
#     finish_tournament_task.apply_async(
#     args=[tournament.id, []],
#     eta=end_time
# )
    schedule_tournament(
    tournament_id=tournament.id,
    start_time=payload.start_time,
    duration_minutes=payload.duration_minutes,
    results=[]  
) 
    db.refresh(tournament)

    return tournament





#join
@router.post("/{tournament_id}/join", response_model=JoinTournamentResponse)
def join_tournament(
    tournament_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tournament = db.query(Tournament).filter_by(id=tournament_id).first()
    if not tournament:
        raise HTTPException(404, "Tournament not found")
    if tournament.status != "UPCOMING":
        raise HTTPException(400, "Tournament already started")

    participant = db.query(TournamentParticipant)\
        .filter_by(tournament_id=tournament.id, user_id=current_user.id)\
        .first()
    if participant:
        raise HTTPException(400, "Already joined")

    paid = False
    if tournament.deposit_required:
        if current_user.balance < tournament.entry_fee:
            raise HTTPException(400, "Insufficient balance")
        current_user.balance -= Decimal(tournament.entry_fee)
        tournament.escrow_balance += Decimal(tournament.entry_fee)
        paid = True
        db.add(Transaction(
            user_id=current_user.id,
            amount=tournament.entry_fee,
            type="TOURNAMENT_JOIN",
            status="COMPLETED",
        ))

    participant = TournamentParticipant(
        tournament_id=tournament.id,
        user_id=current_user.id,
        paid=paid
    )

    db.add(participant)
    db.commit()
    return JoinTournamentResponse(
        tournament_id=tournament.id,
        user_id=current_user.id,
        paid=paid
    )

#cancel
@router.post("/{tournament_id}/cancel")
def cancel_tournament(
    tournament_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tournament = db.query(Tournament).filter_by(id=tournament_id).first()
    if not tournament or tournament.creator_id != current_user.id:
        raise HTTPException(403)
    if tournament.status != "UPCOMING":
        raise HTTPException(400, "Cannot cancel running tournament")

    participants = db.query(TournamentParticipant)\
        .filter_by(tournament_id=tournament.id).all()

    refund_amount = tournament.entry_fee
    for p in participants:
        user = db.query(User).filter_by(id=p.user_id).first()
        if p.paid:
            user.balance += Decimal(refund_amount)
            db.add(Transaction(
                user_id=user.id,
                amount=refund_amount,
                type="TOURNAMENT_REFUND",
                status="COMPLETED"
            ))

    if tournament.deposit_required and tournament.entry_fee > 0:
        creator = db.query(User).filter_by(id=tournament.creator_id).first()
        creator.balance += Decimal(tournament.entry_fee)
        db.add(Transaction(
            user_id=creator.id,
            amount=tournament.entry_fee,
            type="TOURNAMENT_REFUND",
            status="COMPLETED"
        ))

    tournament.status = "CANCELLED"
    tournament.escrow_balance = 0
    db.commit()
    return {"status": "cancelled"}

#finish
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

    if tournament.status != "RUNNING" and tournament.status != "UPCOMING":
        raise HTTPException(400, "Tournament not running")

    rules = tournament.prize_rules
    total = Decimal(tournament.escrow_balance)

    for idx, place in enumerate(rules["places"]):
        user_id = payload.results[place-1]
        share = Decimal(rules["distribution"][idx])
        amount = total * share

        user = db.query(User).filter_by(id=user_id).first()
        if user:
            user.balance += amount
            db.add(Transaction(
                user_id=user_id,
                amount=amount,
                type="TOURNAMENT_WIN",
                status="COMPLETED"
            ))

    tournament.status = "FINISHED"
    tournament.escrow_balance = 0
    db.commit()
    return {"status": "completed"}



#list
@router.get("/list")
def list_tournaments(
    status: str = Query("ALL", description="Filter by status: UPCOMING, RUNNING, FINISHED, CANCELLED"),
    db: Session = Depends(get_db)
):
    """
    List tournaments with optional status filter.
    """
    query = db.query(Tournament)
    
    if status != "ALL":
        query = query.filter(Tournament.status == status.upper())

    tournaments = query.order_by(Tournament.start_time.desc()).all()

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
                "status": t.status,
                "escrow_balance": float(t.escrow_balance),
                "created_at": t.created_at,
            }
            for t in tournaments
        ],
        "count": len(tournaments)
    }

@router.get("/{tournament_id}", response_model=TournamentResponse)
def get_tournament_by_id(
    tournament_id: str,
    db: Session = Depends(get_db),
):
    tournament = db.query(Tournament).filter_by(id=tournament_id).first()

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    return tournament

# get all participants in a tournament
@router.get("/{tournament_id}/participants")
def get_tournament_participants(
    tournament_id: str,
    db: Session = Depends(get_db),
):
    tournament = db.query(Tournament).filter_by(id=tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

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
                "score": p.score,
                "paid": p.paid,
            }
            for p, user in participants
        ],
    }
