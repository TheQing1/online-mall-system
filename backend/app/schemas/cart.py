from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field

class CartItemCreate(BaseModel):
    product_id: int
    sku_id: Optional[int] = None
    quantity: int = Field(1, ge=1)

class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1)

class CartProductOut(BaseModel):
    id: int
    name: str
    image: str = ""

    class Config:
        from_attributes = True

class CartItemOut(BaseModel):
    id: int
    product_id: int
    sku_id: int
    quantity: int
    sku_name: str
    sku_spec: dict = {}
    unit_price: Decimal
    product: CartProductOut

    class Config:
        from_attributes = True

class CartOut(BaseModel):
    items: list[CartItemOut]
    total_count: int
    total_amount: Decimal
