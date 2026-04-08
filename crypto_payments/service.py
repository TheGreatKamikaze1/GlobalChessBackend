from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.models import CryptoRequest, GiftTransfer, User
from core.economy import credit_user_balance, create_transaction_record
from crypto_payments.config import (
    NetworkConfig,
    get_asset_config,
    get_network_config,
    get_supported_networks,
    normalize_address,
)
from gifts.catalog import get_gift_catalog_item

TRANSFER_METHOD_ID = "a9059cbb"


def decimal_to_base_units(amount: Decimal, decimals: int) -> int:
    quantum = Decimal(1) / (Decimal(10) ** decimals)
    normalized = amount.quantize(quantum, rounding=ROUND_HALF_UP)
    return int(normalized * (Decimal(10) ** decimals))


def format_asset_amount(amount: Decimal, decimals: int) -> str:
    quantum = Decimal(1) / (Decimal(10) ** decimals)
    normalized = amount.quantize(quantum, rounding=ROUND_HALF_UP)
    return format(normalized.normalize(), "f")


def pad_hex(value: str) -> str:
    return value.rjust(64, "0")


def encode_erc20_transfer_data(recipient: str, amount_base_units: int) -> str:
    recipient_address = normalize_address(recipient)[2:]
    return f"0x{TRANSFER_METHOD_ID}{pad_hex(recipient_address)}{pad_hex(hex(amount_base_units)[2:])}"


def decode_erc20_transfer_data(data: str) -> tuple[str, int]:
    payload = (data or "").strip().lower()
    if not payload.startswith("0x") or len(payload) < 138:
        raise ValueError("Invalid ERC20 transfer payload")

    method = payload[2:10]
    if method != TRANSFER_METHOD_ID:
        raise ValueError("Unsupported transfer method")

    recipient_chunk = payload[10:74]
    amount_chunk = payload[74:138]

    recipient = normalize_address(recipient_chunk[-40:])
    amount = int(amount_chunk, 16)
    return recipient, amount


def serialize_network(network: NetworkConfig) -> dict[str, Any]:
    return {
        "key": network.key,
        "name": network.name,
        "chainId": network.chain_id,
        "chainIdHex": network.chain_id_hex,
        "currencySymbol": network.currency_symbol,
        "publicRpcUrl": network.public_rpc_url,
        "explorerUrl": network.explorer_url,
        "treasuryAddress": network.treasury_address or None,
        "configured": bool(network.treasury_address),
        "assets": [
            {
                "symbol": asset.symbol,
                "name": asset.name,
                "contractAddress": asset.contract_address,
                "decimals": asset.decimals,
                "usdPrice": format(asset.usd_price, "f"),
            }
            for asset in network.assets.values()
        ],
    }


def serialize_supported_networks() -> list[dict[str, Any]]:
    return [serialize_network(network) for network in get_supported_networks().values()]


def build_crypto_request_payload(request: CryptoRequest) -> dict[str, Any]:
    meta = request.meta or {}
    gift_meta = meta.get("gift") or {}
    tx_meta = meta.get("transaction") or {}
    network = get_supported_networks().get((request.network or "").upper())
    explorer_url = None
    if network and tx_meta.get("txHash"):
        explorer_url = f"{network.explorer_url.rstrip('/')}/tx/{tx_meta['txHash']}"

    return {
        "id": str(request.id),
        "reference": request.reference,
        "kind": request.kind,
        "status": request.status,
        "asset": request.asset,
        "network": request.network,
        "walletAddress": request.wallet_address or tx_meta.get("fromAddress"),
        "amountUsd": float(request.amount_usd),
        "amountCrypto": request.amount_crypto,
        "txHash": tx_meta.get("txHash"),
        "explorerUrl": explorer_url,
        "createdAt": request.created_at,
        "updatedAt": request.updated_at,
        "confirmedAt": request.confirmed_at,
        "linkedGiftTransferId": request.linked_gift_transfer_id,
        "purpose": meta.get("purpose"),
        "gift": (
            {
                "id": gift_meta.get("giftId", ""),
                "name": gift_meta.get("giftName", ""),
                "recipientUsername": gift_meta.get("recipientUsername", ""),
                "note": gift_meta.get("note"),
                "transferId": request.linked_gift_transfer_id,
            }
            if gift_meta
            else None
        ),
        "detail": meta.get("detail"),
    }


def build_checkout_response(request: CryptoRequest) -> dict[str, Any]:
    meta = request.meta or {}
    payment_meta = meta.get("payment") or {}
    gift_meta = meta.get("gift") or {}

    return {
        "reference": request.reference,
        "status": request.status,
        "network": request.network,
        "asset": request.asset,
        "amountUsd": float(request.amount_usd),
        "amountCrypto": request.amount_crypto,
        "recipientUsername": gift_meta.get("recipientUsername"),
        "note": gift_meta.get("note"),
        "treasuryAddress": payment_meta.get("treasuryAddress"),
        "explorerUrl": payment_meta.get("explorerUrl"),
        "tokenContractAddress": payment_meta.get("tokenContractAddress"),
        "tokenDecimals": payment_meta.get("tokenDecimals"),
        "tokenName": payment_meta.get("tokenName"),
        "paymentTransaction": payment_meta.get("transaction"),
        "gift": {
            "id": gift_meta.get("giftId"),
            "name": gift_meta.get("giftName"),
            "piece": gift_meta.get("piece"),
            "description": gift_meta.get("description"),
            "priceUsd": float(request.amount_usd),
        },
    }


def build_wallet_checkout_response(request: CryptoRequest) -> dict[str, Any]:
    meta = request.meta or {}
    payment_meta = meta.get("payment") or {}
    purpose_meta = meta.get("walletDeposit") or {}

    return {
        "reference": request.reference,
        "status": request.status,
        "network": request.network,
        "asset": request.asset,
        "amountUsd": float(request.amount_usd),
        "amountCrypto": request.amount_crypto,
        "treasuryAddress": payment_meta.get("treasuryAddress"),
        "explorerUrl": payment_meta.get("explorerUrl"),
        "tokenContractAddress": payment_meta.get("tokenContractAddress"),
        "tokenDecimals": payment_meta.get("tokenDecimals"),
        "tokenName": payment_meta.get("tokenName"),
        "paymentTransaction": payment_meta.get("transaction"),
        "purpose": purpose_meta.get("purpose") or "wallet_deposit",
    }


def create_gift_checkout(
    *,
    db: Session,
    current_user: User,
    recipient_username: str,
    gift_id: str,
    note: str | None,
    network_key: str,
    asset_symbol: str,
) -> CryptoRequest:
    recipient = db.query(User).filter(User.username == recipient_username.strip()).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    if str(recipient.id) == str(current_user.id):
        raise HTTPException(status_code=400, detail="You cannot send a gift to yourself")

    network = get_network_config(network_key)
    asset = get_asset_config(network_key, asset_symbol)

    if not network.treasury_address:
        raise HTTPException(
            status_code=500,
            detail=f"{network.name} treasury wallet is not configured on the server",
        )

    gift = get_gift_catalog_item(gift_id)
    if not gift:
        raise HTTPException(status_code=404, detail="Gift not found")

    amount_usd = Decimal(str(gift["price_usd"]))
    amount_crypto = (amount_usd / asset.usd_price).quantize(
        Decimal(1) / (Decimal(10) ** asset.decimals),
        rounding=ROUND_HALF_UP,
    )
    amount_base_units = decimal_to_base_units(amount_crypto, asset.decimals)
    reference = f"cg_{uuid.uuid4().hex[:18]}"

    transaction_payload = {
        "chainIdHex": network.chain_id_hex,
        "to": asset.contract_address,
        "value": "0x0",
        "data": encode_erc20_transfer_data(network.treasury_address, amount_base_units),
    }

    request = CryptoRequest(
        user_id=current_user.id,
        linked_gift_transfer_id=None,
        kind="GIFT_PURCHASE",
        reference=reference,
        status="AWAITING_PAYMENT",
        asset=asset.symbol,
        network=network.key,
        wallet_address=None,
        amount_usd=amount_usd,
        amount_crypto=format_asset_amount(amount_crypto, asset.decimals),
        meta={
            "payment": {
                "chainId": network.chain_id,
                "chainIdHex": network.chain_id_hex,
                "treasuryAddress": network.treasury_address,
                "tokenContractAddress": asset.contract_address,
                "tokenDecimals": asset.decimals,
                "tokenName": asset.name,
                "explorerUrl": network.explorer_url,
                "transaction": transaction_payload,
            },
            "gift": {
                "giftId": gift["id"],
                "giftName": gift["name"],
                "piece": gift["piece"],
                "description": gift["description"],
                "recipientId": str(recipient.id),
                "recipientUsername": recipient.username,
                "note": (note or "").strip() or None,
            },
        },
    )

    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def create_wallet_checkout(
    *,
    db: Session,
    current_user: User,
    amount_usd: float,
    network_key: str,
    asset_symbol: str,
) -> CryptoRequest:
    network = get_network_config(network_key)
    asset = get_asset_config(network_key, asset_symbol)

    if not network.treasury_address:
        raise HTTPException(
            status_code=500,
            detail=f"{network.name} treasury wallet is not configured on the server",
        )

    amount_value = Decimal(str(amount_usd))
    amount_crypto = (amount_value / asset.usd_price).quantize(
        Decimal(1) / (Decimal(10) ** asset.decimals),
        rounding=ROUND_HALF_UP,
    )
    amount_base_units = decimal_to_base_units(amount_crypto, asset.decimals)
    reference = f"cw_{uuid.uuid4().hex[:18]}"

    transaction_payload = {
        "chainIdHex": network.chain_id_hex,
        "to": asset.contract_address,
        "value": "0x0",
        "data": encode_erc20_transfer_data(network.treasury_address, amount_base_units),
    }

    request = CryptoRequest(
        user_id=current_user.id,
        linked_gift_transfer_id=None,
        kind="WALLET_DEPOSIT",
        reference=reference,
        status="AWAITING_PAYMENT",
        asset=asset.symbol,
        network=network.key,
        wallet_address=None,
        amount_usd=amount_value,
        amount_crypto=format_asset_amount(amount_crypto, asset.decimals),
        meta={
            "payment": {
                "chainId": network.chain_id,
                "chainIdHex": network.chain_id_hex,
                "treasuryAddress": network.treasury_address,
                "tokenContractAddress": asset.contract_address,
                "tokenDecimals": asset.decimals,
                "tokenName": asset.name,
                "explorerUrl": network.explorer_url,
                "transaction": transaction_payload,
            },
            "purpose": "wallet_deposit",
            "walletDeposit": {
                "amountUsd": float(amount_value),
                "purpose": "wallet_deposit",
            },
        },
    )

    db.add(request)
    db.commit()
    db.refresh(request)
    return request


async def _rpc_call(network: NetworkConfig, method: str, params: list[Any]) -> Any:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            network.public_rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params,
            },
        )
        response.raise_for_status()
        payload = response.json()

    if payload.get("error"):
        raise HTTPException(status_code=502, detail=payload["error"].get("message", "RPC error"))

    return payload.get("result")


async def verify_request_transaction(
    *,
    request: CryptoRequest,
    tx_hash: str,
    from_address: str | None,
) -> dict[str, Any]:
    tx_hash = (tx_hash or "").strip()
    if not tx_hash.startswith("0x") or len(tx_hash) < 66:
        raise HTTPException(status_code=400, detail="Invalid transaction hash")

    network = get_network_config(request.network or "")
    asset = get_asset_config(request.network or "", request.asset or "")

    if not network.treasury_address:
        raise HTTPException(status_code=500, detail="Crypto treasury wallet is not configured")

    transaction = await _rpc_call(network, "eth_getTransactionByHash", [tx_hash])
    if not transaction:
        return {"state": "PENDING", "detail": "Transaction not indexed yet"}

    receipt = await _rpc_call(network, "eth_getTransactionReceipt", [tx_hash])
    if not receipt:
        return {"state": "PENDING", "detail": "Transaction is waiting for confirmation"}

    try:
        tx_from = normalize_address(transaction.get("from"))
        expected_from = normalize_address(from_address) if from_address else tx_from
        if tx_from != expected_from:
            raise HTTPException(
                status_code=400,
                detail="Transaction sender does not match the connected wallet",
            )

        tx_to = normalize_address(transaction.get("to"))
        if tx_to != normalize_address(asset.contract_address):
            raise HTTPException(
                status_code=400,
                detail="Transaction was not sent to the supported token contract",
            )

        recipient, amount_base_units = decode_erc20_transfer_data(transaction.get("input") or "")
        if recipient != normalize_address(network.treasury_address):
            raise HTTPException(
                status_code=400,
                detail="Transaction recipient does not match the platform treasury wallet",
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    expected_amount = decimal_to_base_units(Decimal(str(request.amount_crypto)), asset.decimals)
    if amount_base_units != expected_amount:
        raise HTTPException(status_code=400, detail="Transaction amount does not match the expected gift amount")

    status_hex = (receipt.get("status") or "").lower()
    if status_hex != "0x1":
        raise HTTPException(status_code=400, detail="Transaction reverted on-chain")

    return {
        "state": "COMPLETED",
        "detail": "Crypto payment confirmed on-chain",
        "fromAddress": tx_from,
    }


def settle_verified_gift_request(
    *,
    db: Session,
    request: CryptoRequest,
    from_address: str,
    tx_hash: str,
    detail: str,
) -> CryptoRequest:
    if request.status == "COMPLETED":
        return request

    meta = request.meta or {}
    gift_meta = meta.get("gift") or {}
    recipient_id = gift_meta.get("recipientId")
    if not recipient_id:
        raise HTTPException(status_code=500, detail="Gift recipient metadata is missing")

    gift_transfer = GiftTransfer(
        sender_id=request.user_id,
        recipient_id=recipient_id,
        gift_id=gift_meta.get("giftId"),
        gift_name=gift_meta.get("giftName"),
        piece=gift_meta.get("piece"),
        price_usd=request.amount_usd,
        note=gift_meta.get("note"),
        status="SENT",
        purchase_reference=request.reference,
    )

    db.add(gift_transfer)
    db.flush()

    create_transaction_record(
        db,
        user_id=str(request.user_id),
        amount=request.amount_usd,
        type="CRYPTO_GIFT_PURCHASE",
        reference=request.reference,
        provider="crypto",
        meta={
            "giftTransferId": str(gift_transfer.id),
            "fromAddress": from_address,
            "txHash": tx_hash,
            "detail": detail,
        },
    )

    request.linked_gift_transfer_id = str(gift_transfer.id)
    request.wallet_address = from_address
    request.status = "COMPLETED"
    request.confirmed_at = datetime.now(timezone.utc)
    request.meta = {
        **meta,
        "transaction": {
            **(meta.get("transaction") or {}),
            "txHash": tx_hash,
            "fromAddress": from_address,
        },
        "detail": detail,
    }

    user = db.query(User).filter(User.id == request.user_id).first()
    if user:
        user.wallet_address = from_address
        user.wallet_network = request.network
        user.wallet_verified_at = request.confirmed_at

    db.commit()
    db.refresh(request)
    return request


def settle_verified_wallet_request(
    *,
    db: Session,
    request: CryptoRequest,
    from_address: str,
    tx_hash: str,
    detail: str,
) -> CryptoRequest:
    if request.status == "COMPLETED":
        return request

    user = db.query(User).filter(User.id == request.user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    credit_user_balance(user, request.amount_usd)
    user.wallet_address = from_address
    user.wallet_network = request.network
    user.wallet_verified_at = datetime.now(timezone.utc)

    create_transaction_record(
        db,
        user_id=str(user.id),
        amount=request.amount_usd,
        type="CRYPTO_DEPOSIT",
        reference=request.reference,
        provider="crypto",
        meta={
            "purpose": "wallet_deposit",
            "fromAddress": from_address,
            "txHash": tx_hash,
            "detail": detail,
            "network": request.network,
            "asset": request.asset,
        },
    )

    request.wallet_address = from_address
    request.status = "COMPLETED"
    request.confirmed_at = datetime.now(timezone.utc)
    request.meta = {
        **(request.meta or {}),
        "transaction": {
            **((request.meta or {}).get("transaction") or {}),
            "txHash": tx_hash,
            "fromAddress": from_address,
        },
        "detail": detail,
    }

    db.commit()
    db.refresh(request)
    return request


def mark_request_submitted(
    *,
    db: Session,
    request: CryptoRequest,
    tx_hash: str,
    from_address: str | None,
    status: str,
    detail: str,
) -> CryptoRequest:
    meta = request.meta or {}
    request.status = status
    request.wallet_address = normalize_address(from_address) if from_address else request.wallet_address
    request.meta = {
        **meta,
        "transaction": {
            **(meta.get("transaction") or {}),
            "txHash": tx_hash,
            "fromAddress": normalize_address(from_address) if from_address else None,
        },
        "detail": detail,
    }
    db.commit()
    db.refresh(request)
    return request
