import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.auth import get_current_user_id
from core.database import get_db
from core.economy import create_transaction_record, debit_user_balance, money_to_float, to_money
from core.models import GiftTransfer, User
from gifts.catalog import GIFT_CATALOG, get_gift_catalog_item
from gifts.schemas import (
    GiftCatalogResponse,
    GiftListResponse,
    GiftRecordResponse,
    GiftSummaryResponse,
    SendGiftRequest,
)

router = APIRouter(tags=["Gifts"])


def _gift_user_payload(user: User | None) -> dict:
    if not user:
        return {
            "id": "unknown",
            "username": "unknown",
            "displayName": "Unknown player",
            "avatarUrl": None,
        }

    return {
        "id": str(user.id),
        "username": user.username,
        "displayName": user.display_name,
        "avatarUrl": user.avatar_url,
    }


def _gift_record_payload(db: Session, gift: GiftTransfer) -> dict:
    sender = db.query(User).filter(User.id == gift.sender_id).first()
    recipient = db.query(User).filter(User.id == gift.recipient_id).first()

    return {
        "id": str(gift.id),
        "giftId": gift.gift_id,
        "giftName": gift.gift_name,
        "piece": gift.piece,
        "priceUsd": money_to_float(gift.price_usd),
        "note": gift.note,
        "status": gift.status,
        "redemptionStatus": gift.redemption_status,
        "purchaseReference": gift.purchase_reference,
        "redemptionReference": gift.redemption_reference,
        "createdAt": gift.created_at,
        "redeemedAt": gift.redeemed_at,
        "sender": _gift_user_payload(sender),
        "recipient": _gift_user_payload(recipient),
    }


@router.get("/catalog", response_model=GiftCatalogResponse)
def get_gift_catalog():
    return {
        "success": True,
        "data": [
            {
                "id": gift["id"],
                "name": gift["name"],
                "piece": gift["piece"],
                "description": gift["description"],
                "priceUsd": money_to_float(gift["price_usd"]),
            }
            for gift in GIFT_CATALOG
        ],
    }


@router.get("/summary", response_model=GiftSummaryResponse)
def get_gift_summary(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    sent_count = db.query(GiftTransfer).filter(GiftTransfer.sender_id == user_id).count()
    received_count = db.query(GiftTransfer).filter(GiftTransfer.recipient_id == user_id).count()
    redeemed_count = (
        db.query(GiftTransfer)
        .filter(GiftTransfer.recipient_id == user_id, GiftTransfer.status == "REDEEMED")
        .count()
    )
    pending_settlements = (
        db.query(GiftTransfer)
        .filter(
            GiftTransfer.recipient_id == user_id,
            GiftTransfer.status == "REDEEMED",
            GiftTransfer.redemption_status == "PENDING_CLAIM_REVIEW",
        )
        .count()
    )

    return {
        "success": True,
        "data": {
            "sentCount": sent_count,
            "receivedCount": received_count,
            "redeemedCount": redeemed_count,
            "pendingSettlements": pending_settlements,
            "canGift": True,
            "canRedeem": True,
        },
    }


@router.get("/sent", response_model=GiftListResponse)
def get_sent_gifts(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    gifts = (
        db.query(GiftTransfer)
        .filter(GiftTransfer.sender_id == user_id)
        .order_by(GiftTransfer.created_at.desc())
        .all()
    )
    return {"success": True, "data": [_gift_record_payload(db, gift) for gift in gifts]}


@router.get("/received", response_model=GiftListResponse)
def get_received_gifts(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    gifts = (
        db.query(GiftTransfer)
        .filter(GiftTransfer.recipient_id == user_id)
        .order_by(GiftTransfer.created_at.desc())
        .all()
    )
    return {"success": True, "data": [_gift_record_payload(db, gift) for gift in gifts]}


@router.get("/redeemed", response_model=GiftListResponse)
def get_redeemed_gifts(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    gifts = (
        db.query(GiftTransfer)
        .filter(GiftTransfer.recipient_id == user_id, GiftTransfer.status == "REDEEMED")
        .order_by(GiftTransfer.redeemed_at.desc(), GiftTransfer.created_at.desc())
        .all()
    )
    return {"success": True, "data": [_gift_record_payload(db, gift) for gift in gifts]}


@router.post("/send", response_model=GiftRecordResponse)
def send_gift(
    payload: SendGiftRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    sender = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")

    recipient = db.query(User).filter(User.username == payload.recipientUsername.strip()).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    if str(recipient.id) == str(user_id):
        raise HTTPException(status_code=400, detail="You cannot send a gift to yourself")

    gift = get_gift_catalog_item(payload.giftId)
    if not gift:
        raise HTTPException(status_code=404, detail="Gift not found")

    gift_price = to_money(gift["price_usd"])
    debit_user_balance(sender, gift_price)

    gift_transfer = GiftTransfer(
        sender_id=user_id,
        recipient_id=str(recipient.id),
        gift_id=gift["id"],
        gift_name=gift["name"],
        piece=gift["piece"],
        price_usd=gift_price,
        note=(payload.note or "").strip() or None,
        status="SENT",
        purchase_reference=f"gift_send_{uuid.uuid4().hex[:12]}",
    )

    db.add(gift_transfer)
    db.flush()

    create_transaction_record(
        db,
        user_id=str(sender.id),
        amount=gift_price,
        type="GIFT_PURCHASE",
        reference=f"gift_wallet_{gift_transfer.id}",
        meta={
            "giftTransferId": str(gift_transfer.id),
            "giftId": gift["id"],
            "recipientId": str(recipient.id),
            "recipientUsername": recipient.username,
        },
    )

    db.commit()
    db.refresh(gift_transfer)

    return {"success": True, "data": _gift_record_payload(db, gift_transfer)}


@router.post("/{gift_id}/redeem", response_model=GiftRecordResponse)
def redeem_gift(
    gift_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    gift = (
        db.query(GiftTransfer)
        .filter(GiftTransfer.id == gift_id, GiftTransfer.recipient_id == user_id)
        .first()
    )
    if not gift:
        raise HTTPException(status_code=404, detail="Gift not found")

    if gift.status == "REDEEMED":
        return {"success": True, "data": _gift_record_payload(db, gift)}

    now = datetime.now(timezone.utc)
    gift.status = "REDEEMED"
    gift.redemption_status = "CLAIMED"
    gift.redeemed_at = now
    gift.redemption_reference = f"gift_claim_{uuid.uuid4().hex[:12]}"

    db.commit()
    db.refresh(gift)

    return {"success": True, "data": _gift_record_payload(db, gift)}
