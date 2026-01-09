from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, timedelta

from tournaments.models import Tournament, TournamentParticipant
from core.database import SessionLocal
from core.models import User, Transaction

scheduler = BackgroundScheduler()
scheduler.start()


def start_tournament(tournament_id: str):
    db: Session = SessionLocal()
    tournament = db.query(Tournament).filter_by(id=tournament_id).first()
    if tournament and tournament.status == "UPCOMING":
        tournament.status = "RUNNING"
        db.commit()
    db.close()


def finish_tournament(tournament_id: str, results: list[str]):
    db: Session = SessionLocal()
    tournament = db.query(Tournament).filter_by(id=tournament_id).first()
    if not tournament:
        db.close()
        return

    if tournament.status != "RUNNING":
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
                user_id=user_id,
                amount=amount,
                type="TOURNAMENT_WIN",
                status="COMPLETED"
            ))

    tournament.status = "FINISHED"
    tournament.escrow_balance = 0
    db.commit()
    db.close()


def schedule_tournament(tournament_id: str, start_time: datetime, duration_minutes: int, results: list[str]):
    # Schedule start
    scheduler.add_job(
        start_tournament,
        'date',
        run_date=start_time,
        args=[tournament_id],
        id=f"start_{tournament_id}"
    )

    # Schedule finish
    end_time = start_time + timedelta(minutes=duration_minutes)
    scheduler.add_job(
        finish_tournament,
        'date',
        run_date=end_time,
        args=[tournament_id, results],
        id=f"finish_{tournament_id}"
    )
