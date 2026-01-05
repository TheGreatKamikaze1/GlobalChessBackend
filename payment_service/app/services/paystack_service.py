import hmac
import hashlib
import httpx
from payment_service.app.core.config import settings


async def initialize_payment(email: str, amount: int):
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "email": email,
        "amount": amount,  # Kobo
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.PAYSTACK_BASE_URL}/transaction/initialize",
            json=payload,
            headers=headers,
        )

    if response.status_code != 200:
        raise Exception(response.text)

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
