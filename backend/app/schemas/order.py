from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, field_serializer
from decimal import Decimal

class OrderItemOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    product_image: Optional[str] = None
    price: Decimal
    quantity: int

    class Config:
        from_attributes = True

class OrderOut(BaseModel):
    id: int
    order_no: str
    total_amount: Decimal
    status: str
    address_snapshot: dict
    remark: Optional[str] = None
    items: List[OrderItemOut] = []
    created_at: str

    class Config:
        from_attributes = True

    @field_serializer("created_at")
    @classmethod
    def serialize_created_at(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)

class OrderCreate(BaseModel):
    address_id: int
    remark: Optional[str] = None
