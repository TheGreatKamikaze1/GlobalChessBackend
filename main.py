# main.py (core backend root)
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from core.init_db import init_db
from core.handlers import app_exception_handler
from core.exceptions import AppException

from users.auth import router as auth_router
from game_management.game import router as game_router
from challenges.challenge import router as challenge_router
from transactions.main import router as transaction_router
from stats.main import router as stats_router
from payment_service.app.api.routes.paystack import router as payment_router
from users.users import router as users_router
from tournaments.router import router as tournaments_router

from sockets.game_socket import game_socket


app = FastAPI(
    title="Global Chess API",
    version="1.0.0",
)


@app.on_event("startup")
def on_startup():
    init_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://global-connect-chess.netlify.app",
        
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.add_exception_handler(AppException, app_exception_handler)

app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(game_router, prefix="/api/games", tags=["Games"])
app.include_router(challenge_router, prefix="/api/challenges", tags=["Challenges"])
app.include_router(transaction_router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(users_router, prefix="/api/users", tags=["Users"])
app.include_router(stats_router, prefix="/api/stats", tags=["Statistics"])
app.include_router(payment_router, prefix="/api/payments")

app.include_router(tournaments_router, prefix="/api/tournaments", tags=["Tournaments"])


@app.websocket("/ws/game")
async def websocket_endpoint(websocket: WebSocket):
    await game_socket(websocket)


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "Global Chess API"}
