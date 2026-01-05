import stripe
from payment_service.app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_payment_intent(amount: int, currency: str):
    intent = stripe.PaymentIntent.create(
        amount=amount,
        currency=currency.lower(),
        automatic_payment_methods={"enabled": True},
    )
    return intent
