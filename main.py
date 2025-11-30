
from fastapi import FastAPI
from auth import router
from db import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(router, prefix="/auth")
