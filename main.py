from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from core.init_db import init_db
# from slowapi.middleware import SlowAPIMiddleware

from core.database import engine, Base
from core.handlers import app_exception_handler
from core.exceptions import AppException
# from core.rate_limit import limiter

from users.auth import router as auth_router
from game_management.game import router as game_router
from challenges.challenge import router as challenge_router
from transactions.main import router as transaction_router
from stats.main import router as stats_router

from sockets.game_socket import game_socket


from core.models import Base


Base.metadata.create_all(bind=engine)




app = FastAPI()

@app.on_event("startup")
def on_startup():
    init_db()


app = FastAPI(
    title="Global Chess API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080/dashboard"],  # Replace in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.state.limiter = limiter
# app.add_middleware(SlowAPIMiddleware)


app.add_exception_handler(AppException, app_exception_handler)


app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(game_router, prefix="/api/games", tags=["Games"])
app.include_router(challenge_router, prefix="/api/challenges", tags=["Challenges"])
app.include_router(transaction_router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(stats_router, prefix="/api/stats", tags=["Statistics"])


@app.websocket("/ws/game")
async def websocket_endpoint(websocket: WebSocket):
    await game_socket(websocket)


@app.get("/")
def health_check():
    return {
        "status": "healthy",
        "service": "Global Chess API"
    }
