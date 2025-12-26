
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.database import engine, Base
from auth import router
from users.auth import router as auth_router
from game_management.game import router as game_router
from challenges.challenge import router as challenge_router
from core.handlers import app_exception_handler
from core.exceptions import AppException
from sockets.game_socket import game_socket
from fastapi import WebSocket
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from core.rate_limit import limiter

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Global Chess Production API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with frontend URL
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth")
app.include_router(game_router, prefix="/api/games")
app.include_router(challenge_router, prefix="/api/challenges")

app.include_router(router, prefix="/auth")
from transactions.main import router as transaction_router

app.include_router(transaction_router)
from stats.main import router as stats_router

app.include_router(stats_router)

app = FastAPI()
app.add_exception_handler(AppException, app_exception_handler)


@app.websocket("/ws/game")
async def websocket_endpoint(websocket: WebSocket):
    await game_socket(websocket)


app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
@app.get("/")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}

#stats
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from stats.schemas import DashboardResponse
from stats.stats import get_dashboard_stats
from game_management.dependencies import get_current_user_id # Consolidated auth

router = APIRouter(prefix="/api/stats", tags=["Statistics"])

@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id) # Use the unified ID fetcher
):
    
    data = get_dashboard_stats(db, user_id)
    return {
        "success": True,
        "data": data
    }
    
    #gameman
    
from fastapi import FastAPI
from auth import router as AuthRouter
from game import router as GameRouter
from db import Base, engine



Base.metadata.create_all(bind=engine)


app = FastAPI()


app.include_router(AuthRouter, prefix="/auth", tags=["Auth"])
app.include_router(GameRouter, prefix="/game", tags=["Game"])


@app.get("/")

def read_root():
    return {"message": "Welcome to the Global Chess (FastAPI Backend)"}


#challenges
from fastapi import FastAPI
from auth import router as AuthRouter 
from challenge import router as ChallengeRouter 
from db import Base, engine

import models 

Base.metadata.create_all(bind=engine)

app = FastAPI()

# Include the authentication router
app.include_router(AuthRouter, prefix="/auth", tags=["Authentication"])

# Include the new challenge router
app.include_router(ChallengeRouter, prefix="/challenges", tags=["Challenges"])




