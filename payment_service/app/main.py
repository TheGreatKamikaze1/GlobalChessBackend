from fastapi import FastAPI
from fastapi import APIRouter
from payment_service.app.api.routes import paystack, stripe, webhooks
from payment_service.app.api.routes.paystack import router as payment_router
from payment_service.app.db.base import Base
from payment_service.app.db.session import engine


app = FastAPI(title="Payment Service", version="1.0.0")

Base.metadata.create_all(bind=engine)

app.include_router(paystack.router)
app.include_router(stripe.router)
app.include_router(webhooks.router)
app.include_router(payment_router)

@app.get("/")
def root():
    return {"message": "Payment service running"}
