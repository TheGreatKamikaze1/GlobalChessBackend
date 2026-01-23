import hmac
import hashlib
from decimal import Decimal
import httpx
from payment_service.app.core.config import settings


def _base_url() -> str:
    return str(settings.PAYSTACK_BASE_URL).rstrip("/")


def _auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "GlobalChess-FastAPI",
    }


async def initialize_payment(email: str, amount_naira: float | int | Decimal):
    amount_kobo = int(Decimal(str(amount_naira)) * Decimal("100"))

    payload = {
        "email": email,
        "amount": amount_kobo,
        "currency": "NGN",
    }


    if settings.PAYSTACK_CALLBACK_URL:
        payload["callback_url"] = str(settings.PAYSTACK_CALLBACK_URL)

    base_url = str(settings.PAYSTACK_BASE_URL).rstrip("/")
    url = f"{base_url}/transaction/initialize"

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "GlobalChess-FastAPI",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        raise RuntimeError(f"Paystack error {response.status_code}: {response.text}")

    return response.json()


async def verify_payment(reference: str):
    url = f"{_base_url()}/transaction/verify/{reference}"

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=_auth_headers())

    if response.status_code != 200:
        raise RuntimeError(f"Paystack verify error {response.status_code}: {response.text}")

    return response.json()


def verify_webhook_signature(payload: bytes, signature: str | None) -> bool:
    if not signature:
        return False

    computed_signature = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        payload,
        hashlib.sha512,
    ).hexdigest()

    return hmac.compare_digest(computed_signature, signature)



async def list_banks(country: str = "nigeria", per_page: int = 200):
    url = f"{_base_url()}/bank"
    params = {"country": country, "perPage": per_page}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params, headers=_auth_headers())

    if resp.status_code != 200:
        raise RuntimeError(f"Paystack list_banks error {resp.status_code}: {resp.text}")

    return resp.json()


async def resolve_account_number(account_number: str, bank_code: str):
    url = f"{_base_url()}/bank/resolve"
    params = {"account_number": account_number, "bank_code": bank_code}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params, headers=_auth_headers())

    if resp.status_code != 200:
        raise RuntimeError(f"Paystack resolve_account error {resp.status_code}: {resp.text}")

    return resp.json()


async def create_transfer_recipient(name: str, account_number: str, bank_code: str, currency: str = "NGN"):
    url = f"{_base_url()}/transferrecipient"
    payload = {
        "type": "nuban",
        "name": name,
        "account_number": account_number,
        "bank_code": bank_code,
        "currency": currency,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=_auth_headers())

    if resp.status_code != 200:
        raise RuntimeError(f"Paystack create_recipient error {resp.status_code}: {resp.text}")

    return resp.json()


async def initiate_transfer(amount_naira: Decimal, recipient_code: str, reference: str, reason: str | None = None):
    # Paystack expects kobo for NGN
    amount_kobo = int(Decimal(str(amount_naira)) * Decimal("100"))

    url = f"{_base_url()}/transfer"
    payload = {
        "source": "balance",
        "amount": amount_kobo,
        "recipient": recipient_code,
        "reference": reference,
    }
    if reason:
        payload["reason"] = reason

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=_auth_headers())

    if resp.status_code != 200:
        raise RuntimeError(f"Paystack initiate_transfer error {resp.status_code}: {resp.text}")

    return resp.json()


async def verify_transfer(reference: str):
    url = f"{_base_url()}/transfer/verify/{reference}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_auth_headers())

    if resp.status_code != 200:
        raise RuntimeError(f"Paystack verify_transfer error {resp.status_code}: {resp.text}")

    return resp.json()


async def finalize_transfer(transfer_code: str, otp: str):

    url = f"{_base_url()}/transfer/finalize_transfer"
    payload = {"transfer_code": transfer_code, "otp": otp}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=_auth_headers())

    if resp.status_code != 200:
        raise RuntimeError(f"Paystack finalize_transfer error {resp.status_code}: {resp.text}")

    return resp.json()


async def list_banks(country: str = "nigeria", per_page: int = 200):
    url = f"{_base_url()}/bank"
    params = {"country": country, "perPage": per_page}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params, headers=_auth_headers())

    if resp.status_code != 200:
        raise RuntimeError(f"Paystack list_banks error {resp.status_code}: {resp.text}")

    return resp.json()
