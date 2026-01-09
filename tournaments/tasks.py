from celery import shared_task
from sqlalchemy.orm import Session
from decimal import Decimal
from core.database import SessionLocal
from tournaments.models import Tournament, TournamentParticipant
from core.models import User, Transaction

@shared_task
def start_tournament_task(tournament_id: str):
    db: Session = SessionLocal()
    tournament = db.query(Tournament).filter_by(id=tournament_id).first()
    if tournament and tournament.status == "UPCOMING":
        tournament.status = "RUNNING"
        db.commit()
    db.close()


@shared_task
def finish_tournament_task(tournament_id: str, results: list):
    db: Session = SessionLocal()
    tournament = db.query(Tournament).filter_by(id=tournament_id).first()
    if not tournament or tournament.status != "RUNNING":
        db.close()
        return

    rules = tournament.prize_rules
    total = Decimal(tournament.escrow_balance)

    for idx, place in enumerate(rules["places"]):
        if idx >= len(results):
            break
        user_id = results[place - 1]
        share = Decimal(rules["distribution"][idx])
        amount = total * share

        user = db.query(User).filter_by(id=user_id).first()
        if user:
            user.balance += amount
            db.add(Transaction(
                user_id=user.id,
                amount=amount,
                type="TOURNAMENT_WIN",
                status="COMPLETED"
            ))

    tournament.status = "FINISHED"
    tournament.escrow_balance = 0
    db.commit()
    db.close()
