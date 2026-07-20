from pydantic import BaseModel

class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = 1

class CartItemUpdate(BaseModel):
    quantity: int

class CartProductOut(BaseModel):
    id: int
    name: str
    price: float
    image: str = ""

    class Config:
        from_attributes = True

class CartItemOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    product: CartProductOut

    class Config:
        from_attributes = True

class CartOut(BaseModel):
    items: list[CartItemOut]
    total_count: int
    total_amount: float
