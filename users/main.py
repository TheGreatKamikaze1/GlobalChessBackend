from fastapi import FastAPI
from db import Base, engine
from auth import router as AuthRouter
from users import router as UsersRouter

app = FastAPI()


 

app.include_router(AuthRouter)
app.include_router(UsersRouter)