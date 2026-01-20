import hmac
import hashlib
import httpx
from payment_service.app.core.config import settings


async def initialize_payment(email: str, amount_naira: float):
    amount_kobo = int(float(amount_naira) * 100)

    payload = {
        "email": email,
        "amount": amount_kobo,
        "currency": "NGN",
    }

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
    base_url = str(settings.PAYSTACK_BASE_URL).rstrip("/")
    url = f"{base_url}/transaction/verify/{reference}"

    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=headers)

    if response.status_code != 200:
        raise RuntimeError(response.text)

    return response.json()


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    if not signature:
        return False

    computed_signature = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        payload,
        hashlib.sha512,
    ).hexdigest()

    return hmac.compare_digest(computed_signature, signature)
