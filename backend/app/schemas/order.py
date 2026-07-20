from typing import Optional, List
from pydantic import BaseModel
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

class OrderCreate(BaseModel):
    address_id: int
    remark: Optional[str] = None
