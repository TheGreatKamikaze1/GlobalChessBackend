from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid

from sqlalchemy.orm import Session

from core.models import CryptoRequest, PremiumMembership

PREMIUM_MONTHLY_FEE_USD = Decimal("5.00")
SUPPORTED_RAILS = [
    {"asset": "USDT", "network": "TRC20"},
    {"asset": "USDC", "network": "ERC20"},
    {"asset": "BTC", "network": "BITCOIN"},
    {"asset": "ETH", "network": "ERC20"},
]


def get_membership(db: Session, user_id: str, create_if_missing: bool = False) -> PremiumMembership | None:
    membership = db.query(PremiumMembership).filter(PremiumMembership.user_id == user_id).first()

    if membership is None and create_if_missing:
        membership = PremiumMembership(
            user_id=user_id,
            tier="standard",
            status="inactive",
            monthly_fee_usd=PREMIUM_MONTHLY_FEE_USD,
        )
        db.add(membership)
        db.flush()

    return membership


def is_membership_active(membership: PremiumMembership | None) -> bool:
    if membership is None:
        return False

    if membership.tier != "premium" or membership.status != "active":
        return False

    if membership.expires_at and membership.expires_at < datetime.now(timezone.utc):
        return False

    return True


def membership_payload(membership: PremiumMembership | None) -> dict:
    active = is_membership_active(membership)

    return {
        "isPremium": active,
        "membershipTier": "premium" if active else "standard",
        "walletAddress": membership.wallet_address if membership else None,
        "preferredAsset": membership.preferred_asset if membership else None,
        "preferredNetwork": membership.preferred_network if membership else None,
        "premiumSince": membership.activated_at if active and membership else None,
        "premiumUntil": membership.expires_at if active and membership else None,
        "giftingEnabled": active,
        "monthlyFeeUsd": float((membership.monthly_fee_usd if membership else PREMIUM_MONTHLY_FEE_USD) or PREMIUM_MONTHLY_FEE_USD),
        "paymentStatus": membership.status if membership else "inactive",
    }


def get_membership_payload(db: Session, user_id: str) -> dict:
    return membership_payload(get_membership(db, user_id))


def activate_membership(
    db: Session,
    user_id: str,
    wallet_address: str,
    asset: str,
    network: str,
) -> tuple[PremiumMembership, CryptoRequest]:
    membership = get_membership(db, user_id, create_if_missing=True)
    now = datetime.now(timezone.utc)

    membership.tier = "premium"
    membership.status = "active"
    membership.wallet_address = wallet_address.strip()
    membership.preferred_asset = asset.strip().upper()
    membership.preferred_network = network.strip().upper()
    membership.monthly_fee_usd = PREMIUM_MONTHLY_FEE_USD
    membership.activated_at = now
    membership.expires_at = now + timedelta(days=30)

    request = CryptoRequest(
        user_id=user_id,
        kind="PREMIUM_MEMBERSHIP",
        reference=f"premium_{uuid.uuid4().hex}",
        status="CONFIRMED",
        asset=membership.preferred_asset,
        network=membership.preferred_network,
        wallet_address=membership.wallet_address,
        amount_usd=PREMIUM_MONTHLY_FEE_USD,
        meta={"note": "Simulated premium activation pending real crypto provider integration."},
        confirmed_at=now,
    )

    db.add(request)
    db.flush()

    return membership, request


def deactivate_membership(db: Session, user_id: str) -> PremiumMembership:
    membership = get_membership(db, user_id, create_if_missing=True)

    membership.tier = "standard"
    membership.status = "inactive"
    membership.activated_at = None
    membership.expires_at = None

    db.flush()
    return membership


def create_crypto_request(
    db: Session,
    *,
    user_id: str,
    kind: str,
    amount_usd: Decimal,
    wallet_address: str | None = None,
    asset: str | None = None,
    network: str | None = None,
    linked_gift_transfer_id: str | None = None,
    status: str = "PENDING",
    meta: dict | None = None,
) -> CryptoRequest:
    now = datetime.now(timezone.utc)

    request = CryptoRequest(
        user_id=user_id,
        linked_gift_transfer_id=linked_gift_transfer_id,
        kind=kind,
        reference=f"crypto_{uuid.uuid4().hex}",
        status=status,
        asset=(asset or "").strip().upper() or None,
        network=(network or "").strip().upper() or None,
        wallet_address=wallet_address.strip() if wallet_address else None,
        amount_usd=amount_usd,
        meta=meta or {},
        confirmed_at=now if status == "CONFIRMED" else None,
    )

    db.add(request)
    db.flush()
    return request
