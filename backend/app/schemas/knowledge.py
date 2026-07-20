from typing import Optional
from pydantic import BaseModel

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
