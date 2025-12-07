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




