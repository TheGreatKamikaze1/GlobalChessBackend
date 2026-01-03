from fastapi import FastAPI
from app.api.routes import paystack, stripe, webhooks

app = FastAPI(title="Payment Service", version="1.0.0")

app.include_router(paystack.router)
app.include_router(stripe.router)
app.include_router(webhooks.router)

@app.get("/")
def root():
    return {"message": "Payment service running"}
