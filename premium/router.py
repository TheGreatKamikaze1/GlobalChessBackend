from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.auth import get_current_user_id
from core.database import get_db
from premium.schemas import ActivatePremiumRequest, PremiumConfigResponse, PremiumMembershipResponse
from premium.service import (
    PREMIUM_MONTHLY_FEE_USD,
    SUPPORTED_RAILS,
    activate_membership,
    deactivate_membership,
    get_membership,
    membership_payload,
)

router = APIRouter(tags=["Premium"])


@router.get("/config", response_model=PremiumConfigResponse)
def get_premium_config():
    return {
        "success": True,
        "data": {
            "monthlyFeeUsd": float(PREMIUM_MONTHLY_FEE_USD),
            "supportedRails": SUPPORTED_RAILS,
            "features": [
                "Premium-only gifting",
                "Crypto-ready membership",
                "Gift redemption tracking",
                "Future premium feature expansion",
            ],
        },
    }


@router.get("/me", response_model=PremiumMembershipResponse)
def get_my_membership(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return {"success": True, "data": membership_payload(get_membership(db, user_id))}


@router.post("/activate", response_model=PremiumMembershipResponse)
def activate_my_membership(
    payload: ActivatePremiumRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    membership, crypto_request = activate_membership(
        db,
        user_id=user_id,
        wallet_address=payload.walletAddress,
        asset=payload.asset,
        network=payload.network,
    )
    db.commit()
    db.refresh(membership)

    data = membership_payload(membership)
    data["cryptoReference"] = crypto_request.reference
    return {"success": True, "data": data}


@router.post("/deactivate", response_model=PremiumMembershipResponse)
def deactivate_my_membership(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    membership = deactivate_membership(db, user_id)
    db.commit()
    db.refresh(membership)
    return {"success": True, "data": membership_payload(membership)}
