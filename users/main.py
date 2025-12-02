from fastapi import FastAPI
from db import Base, engine
from auth import router as AuthRouter
from users import router as UsersRouter

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.include_router(AuthRouter)
app.include_router(UsersRouter)
