from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from sqlalchemy import or_
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from tournaments.models import Tournament, TournamentParticipant
from core.database import SessionLocal
from core.models import User, Transaction

scheduler = BackgroundScheduler(timezone="UTC")
scheduler.start()


def start_tournament(tournament_id: str):
    db: Session = SessionLocal()
    try:
        # lock row to avoid race conditions
        tournament = (
            db.query(Tournament)
            .filter_by(id=tournament_id)
            .with_for_update()
            .first()
        )
        if not tournament:
            return

        if tournament.status != "UPCOMING":
            return

        now = datetime.now(timezone.utc)
        if tournament.start_time <= now:
            tournament.status = "RUNNING"
            db.commit()
    finally:
        db.close()


def finish_tournament(tournament_id: str):
    db: Session = SessionLocal()
    try:
        # lock row so we don't pay twice
        tournament = (
            db.query(Tournament)
            .filter_by(id=tournament_id)
            .with_for_update()
            .first()
        )
        if not tournament:
            return

        # don't touch cancelled/finished tournaments
        if tournament.status in ("CANCELLED", "FINISHED"):
            return

        now = datetime.now(timezone.utc)
        end_time = tournament.start_time + timedelta(minutes=int(tournament.duration_minutes))

        # only finish when time is actually over
        if now < end_time:
            return

        # collect results by score (desc), joined_at (asc) for tie-breaking
        participants = (
            db.query(TournamentParticipant)
            .filter_by(tournament_id=tournament_id)
            .order_by(TournamentParticipant.score.desc(), TournamentParticipant.joined_at.asc())
            .all()
        )
        results = [p.user_id for p in participants]

        rules = tournament.prize_rules or {}
        places = rules.get("places", [])
        distribution = rules.get("distribution", [])

        total = Decimal(str(tournament.escrow_balance or 0))
        paid_total = Decimal("0")

        # payout
        for idx, place in enumerate(places):
            if idx >= len(distribution):
                break

            rank_index = place - 1
            if rank_index < 0 or rank_index >= len(results):
                continue

            user_id = results[rank_index]
            share = Decimal(str(distribution[idx] or 0))
            amount = (total * share).quantize(Decimal("0.01"))

            if amount <= 0:
                continue

            user = db.query(User).filter_by(id=user_id).first()
            if user:
                user.balance += amount
                paid_total += amount
                db.add(Transaction(
                    user_id=user_id,
                    amount=amount,
                    type="TOURNAMENT_WIN",
                    status="COMPLETED"
                ))

        # refund leftover (if distribution doesn't sum to 1.0)
        leftover = (total - paid_total).quantize(Decimal("0.01"))
        if leftover > 0:
            creator = db.query(User).filter_by(id=tournament.creator_id).first()
            if creator:
                creator.balance += leftover
                db.add(Transaction(
                    user_id=creator.id,
                    amount=leftover,
                    type="TOURNAMENT_REFUND",
                    status="COMPLETED"
                ))

        tournament.status = "FINISHED"
        tournament.escrow_balance = Decimal("0.00")
        db.commit()
    finally:
        db.close()


def schedule_tournament(tournament_id: str, start_time: datetime, duration_minutes: int):
    # Schedule start
    scheduler.add_job(
        start_tournament,
        "date",
        run_date=start_time,
        args=[tournament_id],
        id=f"start_{tournament_id}",
        replace_existing=True,
        misfire_grace_time=300,
    )
