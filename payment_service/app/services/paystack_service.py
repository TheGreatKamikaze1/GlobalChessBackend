import hmac
import hashlib
import httpx
from payment_service.app.core.config import settings


async def initialize_payment(email: str, amount_naira: float):
    amount_kobo = int(amount_naira * 100)

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
        "User-Agent": "FastAPI-Paystack-Test",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        raise RuntimeError(
            f"Paystack error {response.status_code}: {response.text}"
        )

    return response.json()




async def verify_payment(reference: str):
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{settings.PAYSTACK_BASE_URL}/transaction/verify/{reference}",
            headers=headers,
        )

    if response.status_code != 200:
        raise Exception(response.text)

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
