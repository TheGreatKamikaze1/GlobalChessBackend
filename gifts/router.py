from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.auth import get_current_user_id
from core.database import get_db
from core.models import GiftTransfer, User
from gifts.catalog import GIFT_CATALOG, get_gift_catalog_item
from gifts.schemas import (
    GiftCatalogResponse,
    GiftListResponse,
    GiftRecordResponse,
    GiftSummaryResponse,
    SendGiftRequest,
)
from premium.service import create_crypto_request, get_membership, is_membership_active

router = APIRouter(tags=["Gifts"])


def _gift_user_payload(db: Session, user: User) -> dict:
    membership = get_membership(db, str(user.id))
    return {
        "id": str(user.id),
        "username": user.username,
        "displayName": user.display_name,
        "avatarUrl": user.avatar_url,
        "isPremium": is_membership_active(membership),
    }


def _gift_record_payload(db: Session, gift: GiftTransfer) -> dict:
    sender = db.query(User).filter(User.id == gift.sender_id).first()
    recipient = db.query(User).filter(User.id == gift.recipient_id).first()

    return {
        "id": str(gift.id),
        "giftId": gift.gift_id,
        "giftName": gift.gift_name,
        "piece": gift.piece,
        "priceUsd": float(gift.price_usd),
        "note": gift.note,
        "status": gift.status,
        "redemptionStatus": gift.redemption_status,
        "purchaseReference": gift.purchase_reference,
        "redemptionReference": gift.redemption_reference,
        "createdAt": gift.created_at,
        "redeemedAt": gift.redeemed_at,
        "sender": _gift_user_payload(db, sender),
        "recipient": _gift_user_payload(db, recipient),
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
                "priceUsd": float(gift["price_usd"]),
            }
            for gift in GIFT_CATALOG
        ],
    }


@router.get("/summary", response_model=GiftSummaryResponse)
def get_gift_summary(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    membership = get_membership(db, user_id)
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
            GiftTransfer.redemption_status == "PENDING_CRYPTO_SETTLEMENT",
        )
        .count()
    )

    can_use_gifts = is_membership_active(membership)

    return {
        "success": True,
        "data": {
            "sentCount": sent_count,
            "receivedCount": received_count,
            "redeemedCount": redeemed_count,
            "pendingSettlements": pending_settlements,
            "canGift": can_use_gifts,
            "canRedeem": can_use_gifts,
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
    sender = db.query(User).filter(User.id == user_id).first()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")

    sender_membership = get_membership(db, user_id)
    if not is_membership_active(sender_membership):
        raise HTTPException(status_code=403, detail="Premium membership is required to send gifts")

    recipient = (
        db.query(User)
        .filter(User.username == payload.recipientUsername.strip())
        .first()
    )
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    if str(recipient.id) == str(user_id):
        raise HTTPException(status_code=400, detail="You cannot send a gift to yourself")

    recipient_membership = get_membership(db, str(recipient.id))
    if not is_membership_active(recipient_membership):
        raise HTTPException(
            status_code=400,
            detail="Recipient must have active premium membership to receive gifts",
        )

    gift = get_gift_catalog_item(payload.giftId)
    if not gift:
        raise HTTPException(status_code=404, detail="Gift not found")

    purchase_request = create_crypto_request(
        db,
        user_id=user_id,
        kind="GIFT_PURCHASE",
        amount_usd=Decimal(str(gift["price_usd"])),
        wallet_address=sender_membership.wallet_address if sender_membership else None,
        asset=(sender_membership.preferred_asset if sender_membership else None) or "USDT",
        network=(sender_membership.preferred_network if sender_membership else None) or "TRC20",
        status="CONFIRMED",
        meta={"giftId": gift["id"], "recipientId": str(recipient.id)},
    )

    gift_transfer = GiftTransfer(
        sender_id=user_id,
        recipient_id=str(recipient.id),
        gift_id=gift["id"],
        gift_name=gift["name"],
        piece=gift["piece"],
        price_usd=Decimal(str(gift["price_usd"])),
        note=(payload.note or "").strip() or None,
        status="SENT",
        purchase_reference=purchase_request.reference,
    )

    db.add(gift_transfer)
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

    membership = get_membership(db, user_id)
    if not is_membership_active(membership):
        raise HTTPException(status_code=403, detail="Premium membership is required to redeem gifts")

    if not membership or not membership.wallet_address:
        raise HTTPException(status_code=400, detail="Save a crypto wallet before redeeming gifts")

    if gift.status == "REDEEMED":
        return {"success": True, "data": _gift_record_payload(db, gift)}

    now = datetime.now(timezone.utc)
    crypto_request = create_crypto_request(
        db,
        user_id=user_id,
        linked_gift_transfer_id=str(gift.id),
        kind="GIFT_REDEMPTION",
        amount_usd=gift.price_usd,
        wallet_address=membership.wallet_address,
        asset=membership.preferred_asset or "USDT",
        network=membership.preferred_network or "TRC20",
        status="PENDING",
        meta={"giftId": gift.gift_id, "note": "Awaiting manual crypto settlement."},
    )

    gift.status = "REDEEMED"
    gift.redemption_status = "PENDING_CRYPTO_SETTLEMENT"
    gift.redeemed_at = now
    gift.redemption_reference = crypto_request.reference

    db.commit()
    db.refresh(gift)

    return {"success": True, "data": _gift_record_payload(db, gift)}
