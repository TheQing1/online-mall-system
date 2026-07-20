from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, field_serializer
from decimal import Decimal

class CategoryOut(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None
    sort: int
    children: List[CategoryOut] = []

    class Config:
        from_attributes = True

class ProductOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: Decimal
    stock: int
    images: List[str] = []
    status: str
    sales: int
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True

    @field_serializer("created_at")
    @classmethod
    def serialize_created_at(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal
    stock: int = 0
    category_id: Optional[int] = None
    status: str = "on"

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    stock: Optional[int] = None
    category_id: Optional[int] = None
    status: Optional[str] = None

class CategoryCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None
    sort: int = 0

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    sort: Optional[int] = None
