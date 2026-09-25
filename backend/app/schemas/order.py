from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, field_validator
from decimal import Decimal

class OrderItemOut(BaseModel):
    id: int
    product_id: int
    sku_id: int
    sku_name: str
    sku_spec: dict = {}
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
    paid_at: Optional[str] = None
    refund_reason: Optional[str] = None
    refund_note: Optional[str] = None
    refunded_at: Optional[str] = None
    items: List[OrderItemOut] = []
    created_at: str

    class Config:
        from_attributes = True

    @field_validator("created_at", mode="before")
    @classmethod
    def coerce_created_at(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v) if v else ""

    @field_validator("paid_at", "refunded_at", mode="before")
    @classmethod
    def coerce_optional_dt(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v) if v else None

class OrderCreate(BaseModel):
    address_id: int
    remark: Optional[str] = None

class RefundCreate(BaseModel):
    reason: str

class RefundReview(BaseModel):
    approve: bool
    note: Optional[str] = None
