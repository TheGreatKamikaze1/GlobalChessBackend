from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, inspect
from datetime import datetime, timedelta
from typing import List
from db import get_db 
from models import User, Challenge, Game
from challenge_schema import CreateChallengeSchema, AvailableChallenge, MyChallenge, UserMini, ChallengeList
from middleware import get_current_user_id, get_current_user 

router = APIRouter()


def orm_to_dict(obj, follow_rels: List[str] = None):
    data = {}
    for column in obj.__table__.columns:
        data[column.key] = getattr(obj, column.key)

    if follow_rels:
        mapper = inspect(obj).mapper
        for rel in follow_rels:
            if rel in mapper.relationships:
                related_obj = getattr(obj, rel)
                if related_obj:
                    
                    user_data = {
                        "id": related_obj.id,
                        "username": related_obj.username,
                        "displayName": related_obj.display_name,
                    }
                    data[rel] = user_data
    return data


@router.post("/", status_code=201)
async def create_challenge(
    req: CreateChallengeSchema,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
   
    user = db.query(User).filter(User.id == user_id).with_for_update().first() 

    if not user or user.balance < req.stake:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": {"code": "INSUFFICIENT_BALANCE", "message": "Insufficient balance"}
            }
        )

   

    # the challange expires in 1 hr
    expires_at = datetime.utcnow() + timedelta(hours=1) 
    
    new_challenge = Challenge(
        creator_id=user_id,
        stake=req.stake,
        expires_at=expires_at,
        time_control="60/0", 
        status="OPEN"
    )
    db.add(new_challenge)
    db.commit()
    db.refresh(new_challenge)

    #  return response 
    return {
        "success": True,
        "data": {
            "id": new_challenge.id,
            "creatorId": new_challenge.creator_id,
            "stake": new_challenge.stake,
            "timeControl": new_challenge.time_control,
            "status": new_challenge.status,
            "createdAt": new_challenge.created_at,
            "expiresAt": new_challenge.expires_at,
        }
    }




@router.get("/available", response_model=ChallengeList)
async def get_available_challenges(
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    
    challenges = db.query(Challenge)\
        .filter(Challenge.status == "OPEN")\
        .offset(offset)\
        .limit(limit)\
        .all()
    
  
    total = db.query(Challenge).filter(Challenge.status == "OPEN").count()

   
    challenge_data = []
    for challenge in challenges:
      
        creator_mini = UserMini(
            id=challenge.creator.id, 
            username=challenge.creator.username, 
            displayName=challenge.creator.display_name 
        )
        
       
        challenge_data.append(AvailableChallenge(
            id=challenge.id,
            creatorId=challenge.creator_id,
            stake=challenge.stake,
            timeControl=challenge.time_control,
            status=challenge.status,
            createdAt=challenge.created_at,
            expiresAt=challenge.expires_at,
            creator=creator_mini
        ))
    
    return {
        "success": True,
        "data": challenge_data,
        "pagination": {"total": total, "limit": limit, "offset": offset}
    }




@router.get("/my")
async def get_my_challenges(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
   
    challenges = db.query(Challenge)\
        .filter(Challenge.creator_id == user_id)\
        .all()

    # Format output
    challenge_data = [
        MyChallenge.model_validate(c, context={'acceptor': c.acceptor})
        for c in challenges
    ]

    return {"success": True, "data": challenge_data}


@router.post("/{challenge_id}/accept")
async def accept_challenge(
    challenge_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
   
    try:
        # check challenge existence and status
        challenge = db.query(Challenge).filter(Challenge.id == challenge_id).with_for_update().first()
        
        if not challenge:
            raise HTTPException(
                status_code=404,
                detail={"success": False, "error": {"code": "CHALLENGE_NOT_FOUND", "message": "Challenge not found"}}
            )
        
        if challenge.status != "OPEN":
            raise HTTPException(
                status_code=400,
                detail={"success": False, "error": {"code": "CHALLENGE_NOT_AVAILABLE", "message": "Challenge is not available"}}
            )
        
        # prevent accepting your own challenge
        if challenge.creator_id == user_id:
             raise HTTPException(
                status_code=400,
                detail={"success": False, "error": {"code": "INVALID_ACTION", "message": "Cannot accept your own challenge"}}
            )

        # check acceptor balance
        acceptor = db.query(User).filter(User.id == user_id).with_for_update().first()
        
        if not acceptor or acceptor.balance < challenge.stake:
            raise HTTPException(
                status_code=400,
                detail={"success": False, "error": {"code": "INSUFFICIENT_BALANCE", "message": "Insufficient balance"}}
            )
            
       

        # create game
        new_game = Game(
            challenge_id=challenge_id,
            white_id=challenge.creator_id,
            black_id=user_id,
            stake=challenge.stake,
        )
        db.add(new_game)

        # update challenge
        challenge.status = "ACCEPTED"
        challenge.acceptor_id = user_id
        
        db.commit()
        db.refresh(new_game)
        
        return {
            "success": True,
            "data": {
                "challengeId": challenge_id,
                "gameId": new_game.id,
                "status": "ACCEPTED",
                "message": "Challenge accepted. Game started!",
            }
        }
    except Exception as e:
        db.rollback()
        raise e


@router.post("/{challenge_id}/cancel")
async def cancel_challenge(
    challenge_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
   
    try:
        #  Check challenge existence
        challenge = db.query(Challenge).filter(Challenge.id == challenge_id).with_for_update().first()
        
        if not challenge:
            raise HTTPException(
                status_code=404,
                detail={"success": False, "error": {"code": "CHALLENGE_NOT_FOUND", "message": "Challenge not found"}}
            )

        
        if challenge.creator_id != user_id:
            raise HTTPException(
                status_code=403,
                detail={"success": False, "error": {"code": "FORBIDDEN", "message": "Forbidden"}}
            )
        
        #  Cancel the challenge (Update status)
        challenge.status = "CANCELLED"
        db.commit()
        
        return {
            "success": True, 
            "message": "Challenge cancelled successfully"
        }
    except Exception as e:
        db.rollback()
        raise e