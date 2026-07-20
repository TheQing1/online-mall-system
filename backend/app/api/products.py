from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import PageResponse
from app.schemas.product import ProductOut, CategoryOut
from app.services import product_service

router = APIRouter()

@router.get("", response_model=PageResponse[ProductOut])
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    category_id: Optional[int] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
):
    """商品列表：支持搜索、分类筛选、排序、分页"""
    result = product_service.get_products(
        db, page=page, page_size=page_size,
        keyword=keyword, category_id=category_id,
        sort_by=sort_by, sort_order=sort_order,
    )
    return result

@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    """获取分类树"""
    return product_service.get_categories(db)

@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    """商品详情"""
    product = product_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")
    return product
