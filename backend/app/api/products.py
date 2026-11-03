from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.ratelimit import rate_limit
from app.schemas.common import PageResponse
from app.schemas.product import ProductOut, CategoryOut
from app.services import product_service, search

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


# 注意：这条必须放在 `/{product_id}` **之前**。
# FastAPI 按注册顺序匹配，如果 /suggest 在后面，会被 `/{product_id}` 抢先匹配，
# 然后因为「suggest 不是整数」而 422——这是个很容易踩的路由顺序坑。
@router.get(
    "/suggest",
    # 自动补全的调用频率远高于普通搜索（每敲一个字一次），
    # 必须单独限流，否则它会成为绕过全站配额的入口。
    dependencies=[Depends(rate_limit("suggest"))],
)
def suggest_search(
    q: str = Query("", max_length=50, description="用户已输入的内容"),
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """搜索建议（自动补全）。

    与 `/products?keyword=` 的区别：那条是**找全**（走同义词、AND→OR 兜底），
    这条是**补全**（只要字面前缀/子串命中，不扩展到近义词）——
    给错候选比没候选更糟，用户会顺着它搜出一个空结果页。
    """
    return {"items": search.suggest(q, limit=limit, db=db)}

@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    """商品详情"""
    product = product_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")
    return product
