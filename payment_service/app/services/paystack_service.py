import httpx
from app.core.config import settings

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
