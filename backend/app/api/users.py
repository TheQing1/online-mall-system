from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.schemas.user import UserUpdate, AddressCreate, AddressOut
from app.schemas.product import ProductOut
from app.schemas.common import PageResponse, MessageResponse
from app.services import user_service, favorite_service

router = APIRouter()

@router.put("/profile", response_model=MessageResponse)
def update_profile(data: UserUpdate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    user_service.update_profile(db, current_user, data.model_dump(exclude_none=True))
    return {"message": "更新成功"}

# --- Address endpoints ---

@router.get("/addresses", response_model=list[AddressOut])
def list_addresses(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return user_service.get_addresses(db, current_user)

@router.post("/addresses", response_model=AddressOut)
def create_address(data: AddressCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return user_service.create_address(db, current_user, data.model_dump())

@router.put("/addresses/{address_id}", response_model=AddressOut)
def update_address(address_id: int, data: AddressCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    addr = user_service.update_address(db, address_id, current_user, data.model_dump())
    if not addr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在")
    return addr

@router.delete("/addresses/{address_id}", response_model=MessageResponse)
def delete_address(address_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    ok = user_service.delete_address(db, address_id, current_user)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在")
    return {"message": "删除成功"}


# --- Favorites ---


@router.get("/favorites", response_model=PageResponse[ProductOut])
def list_favorites(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return favorite_service.get_favorite_products(db, current_user, page, page_size)


@router.post("/favorites/{product_id}", response_model=MessageResponse)
def add_favorite(
    product_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    favorite_service.add_favorite(db, current_user, product_id)
    return {"message": "收藏成功"}


@router.delete("/favorites/{product_id}", response_model=MessageResponse)
def remove_favorite(
    product_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ok = favorite_service.remove_favorite(db, current_user, product_id)
    if not ok:
        raise HTTPException(status_code=404, detail="收藏不存在")
    return {"message": "已取消收藏"}
