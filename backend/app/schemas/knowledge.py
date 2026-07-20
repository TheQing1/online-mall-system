from typing import Optional
from datetime import datetime
from pydantic import BaseModel, field_validator

class KnowledgeDocCreate(BaseModel):
    title: str
    content: str
    category: str = "other"

class KnowledgeDocUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None

class KnowledgeDocOut(BaseModel):
    id: int
    title: str
    content: str
    category: str
    created_at: str

    class Config:
        from_attributes = True

    @field_validator("created_at", mode="before")
    @classmethod
    def coerce_created_at(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v) if v else ""
