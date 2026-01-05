from fastapi import FastAPI
from fastapi import APIRouter
from app.api.routes import paystack, stripe, webhooks
from app.api.routes.paystack import router as payment_router

app = FastAPI(title="Payment Service", version="1.0.0")

app.include_router(paystack.router)
app.include_router(stripe.router)
app.include_router(webhooks.router)
app.include_router(payment_router)

@app.get("/")
def root():
    return {"message": "Payment service running"}
