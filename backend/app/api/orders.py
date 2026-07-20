from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.schemas.order import OrderCreate, OrderOut
from app.schemas.common import PageResponse, MessageResponse
from app.services import order_service

router = APIRouter()

@router.post("", response_model=OrderOut)
def create_order(data: OrderCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return order_service.create_order(db, current_user, data.address_id, data.remark)

@router.get("", response_model=PageResponse[OrderOut])
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return order_service.get_user_orders(db, current_user, page, page_size)

@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    order = order_service.get_order(db, order_id, current_user)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    return order

@router.put("/{order_id}/cancel", response_model=MessageResponse)
def cancel_order(order_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    order = order_service.cancel_order(db, order_id, current_user)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    return {"message": "订单已取消"}
