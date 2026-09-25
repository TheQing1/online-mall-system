from typing import TypeVar, Generic
from pydantic import BaseModel

T = TypeVar("T")

class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    message: str
