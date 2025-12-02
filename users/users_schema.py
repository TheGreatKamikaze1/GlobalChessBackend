from pydantic import BaseModel

class UpdateProfileSchema(BaseModel):
    displayName: str | None = None
    avatarUrl: str | None = None
