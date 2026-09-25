from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.schemas.cart import CartItemCreate, CartItemUpdate, CartOut
from app.schemas.common import MessageResponse
from app.services import cart_service

router = APIRouter()

@router.get("", response_model=CartOut)
def get_cart(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return cart_service.get_cart(db, current_user)

@router.post("/items", response_model=CartOut)
def add_item(data: CartItemCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    cart_service.add_cart_item(
        db, current_user, data.product_id, data.quantity, data.sku_id
    )
    return cart_service.get_cart(db, current_user)

@router.put("/items/{item_id}", response_model=CartOut)
def update_item(item_id: int, data: CartItemUpdate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    cart_service.update_cart_item(db, item_id, current_user, data.quantity)
    return cart_service.get_cart(db, current_user)

@router.delete("/items/{item_id}", response_model=MessageResponse)
def delete_item(item_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    ok = cart_service.delete_cart_item(db, item_id, current_user)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="购物车项不存在")
    return {"message": "删除成功"}
