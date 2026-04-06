
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from core.init_db import init_db
from core.handlers import app_exception_handler
from core.exceptions import AppException

from users.auth import router as auth_router
from game_management.game import router as game_router
from challenges.challenge import router as challenge_router
from stats.main import router as stats_router
from users.users import router as users_router
from social.search import router as search_router
from social.friends import router as friends_router
from social.chat import router as chat_router
from sockets.voice_chat import voice_router
from sockets.game_socket import game_socket
from gifts.router import router as gifts_router
from puzzles.router import router as puzzles_router
from crypto_payments.router import router as crypto_router


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
        "http://localhost:8080",
        "https://global-connect-chess.netlify.app",
        "https://teal-halva-4a5e7d.netlify.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.add_exception_handler(AppException, app_exception_handler)

app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(game_router, prefix="/api/games", tags=["Games"])
app.include_router(challenge_router, prefix="/api/challenges", tags=["Challenges"])
app.include_router(users_router, prefix="/api/users", tags=["Users"])
app.include_router(stats_router, prefix="/api/stats", tags=["Statistics"])
app.include_router(search_router)
app.include_router(friends_router)
app.include_router(chat_router)
app.include_router(voice_router)
app.include_router(gifts_router, prefix="/api/gifts", tags=["Gifts"])
app.include_router(puzzles_router, prefix="/api/puzzles", tags=["Puzzles"])
app.include_router(crypto_router, prefix="/api/crypto", tags=["Crypto"])


@app.websocket("/ws/game")
async def websocket_endpoint(websocket: WebSocket):
    await game_socket(websocket)


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "Global Chess API"}

