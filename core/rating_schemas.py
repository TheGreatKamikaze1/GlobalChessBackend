from pydantic import BaseModel


class RatingStats(BaseModel):
    overall: int = 1200
    bullet: int = 1200
    blitz: int = 1200
    rapid: int = 1200
    classical: int = 1200
