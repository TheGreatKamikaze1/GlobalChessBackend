
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