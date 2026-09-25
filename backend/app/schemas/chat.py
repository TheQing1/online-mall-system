from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str

    class Config:
        from_attributes = True

    @field_validator("created_at", mode="before")
    @classmethod
    def coerce_created_at(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v) if v else ""
