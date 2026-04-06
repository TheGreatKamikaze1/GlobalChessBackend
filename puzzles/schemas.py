from pydantic import BaseModel, Field


class PuzzleAdvanceRequest(BaseModel):
    attempt_id: str | None = None
    skip_active: bool = False
    mode: str = "mixed"
    allowed_themes: list[str] = Field(default_factory=list)
    excluded_themes: list[str] = Field(default_factory=list)


class PuzzleHintRequest(BaseModel):
    attempt_id: str


class PuzzleMoveRequest(BaseModel):
    attempt_id: str
    move: str


class PuzzleRetryRequest(BaseModel):
    attempt_id: str


class PuzzleCompleteRequest(BaseModel):
    attempt_id: str
    outcome: str = "reviewed"
