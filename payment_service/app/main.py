from fastapi import FastAPI

from payment_service.app.models.payment import Payment  

from payment_service.app.db.base import Base
from payment_service.app.db.session import engine

from payment_service.app.api.routes import paystack, stripe, webhooks

app = FastAPI(title="Payment Service", version="1.0.0")


Base.metadata.create_all(bind=engine)

# ✅ INCLUDE ROUTERS ONCE
app.include_router(paystack.router)
app.include_router(stripe.router)
app.include_router(webhooks.router)

@app.get("/")
def root():
    return {"message": "Payment service running"}
