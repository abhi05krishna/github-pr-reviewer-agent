from typing import Literal, Optional
from pydantic import BaseModel, Field

Severity = Literal["nit", "suggestion", "warning", "blocking"]
Verdict = Literal["approve", "comment", "request_changes"]


class ReviewComment(BaseModel):
    file: str = Field(max_length=300)
    line: Optional[int] = Field(default=None, ge=1)
    severity: Severity
    message: str = Field(min_length=1, max_length=2000)
    in_diff: bool = False  # computed by our code, never trusted from the model


class Review(BaseModel):
    summary: str = Field(min_length=1, max_length=3000)
    verdict: Verdict
    comments: list[ReviewComment] = Field(default_factory=list, max_length=50)
    suspicious_content: bool = False
    suspicious_note: Optional[str] = Field(default=None, max_length=1000)
    degraded: bool = False   # True when the agent failed and this is only a placeholder