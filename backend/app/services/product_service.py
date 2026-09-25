from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.models.product import Product, Category, ProductStatus
from app.models.sku import ProductSku


def _apply_skus(
    product: Product, skus_data: Optional[List[dict]], allow_remove: bool = True
) -> None:
    """重建商品的 SKU，并同步商品级价格/库存聚合值。"""
    if skus_data is None:
        return

    existing_by_id = {sku.id: sku for sku in product.skus}
    kept_ids = set()

    for sku_item in skus_data:
        sku_id = sku_item.get("id")
        if sku_id and sku_id in existing_by_id:
            sku = existing_by_id[sku_id]
            sku.name = sku_item["name"]
            sku.specs = sku_item.get("specs") or {}
            sku.price = sku_item["price"]
            sku.stock = sku_item.get("stock") or 0
            kept_ids.add(sku_id)
        else:
            product.skus.append(
                ProductSku(
                    name=sku_item["name"],
                    specs=sku_item.get("specs") or {},
                    price=sku_item["price"],
                    stock=sku_item.get("stock") or 0,
                )
            )

    if allow_remove:
        for old in list(product.skus):
            if old.id not in kept_ids:
                product.skus.remove(old)

    _sync_product_aggregates(product)


def _sync_product_aggregates(product: Product) -> None:
    """用 SKU 汇总商品默认展示价与总库存。"""
    if product.skus:
        product.price = min(sku.price for sku in product.skus)
        product.stock = sum(sku.stock for sku in product.skus)


def _ensure_default_sku(product: Product) -> None:
    if not product.skus:
        product.skus.append(
            ProductSku(
                name="默认规格",
                specs={},
                price=product.price,
                stock=product.stock,
            )
        )


def get_products(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    category_id: Optional[int] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    """公开商品列表（仅上架），支持搜索、分类筛选、排序、分页。"""
    query = (
        db.query(Product)
        .options(selectinload(Product.skus))
        .filter(Product.status == ProductStatus.ON)
    )

    if keyword:
        query = query.outerjoin(Category, Product.category_id == Category.id).filter(
            or_(
                Product.name.ilike(f"%{keyword}%"),
                Product.description.ilike(f"%{keyword}%"),
                Category.name.ilike(f"%{keyword}%"),
            )
        )

    if category_id:
        sub_ids = [category_id]
        sub_categories = (
            db.query(Category).filter(Category.parent_id == category_id).all()
        )
        sub_ids.extend([c.id for c in sub_categories])
        query = query.filter(Product.category_id.in_(sub_ids))

    valid_sort_columns = ["created_at", "price", "sales", "stock"]
    if sort_by not in valid_sort_columns:
        sort_by = "created_at"
    sort_column = getattr(Product, sort_by, Product.created_at)

    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    for item in items:
        if item.category:
            item.category_name = item.category.name

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_product(db: Session, product_id: int) -> Optional[Product]:
    """商品详情（仅上架）。"""
    return (
        db.query(Product)
        .options(selectinload(Product.skus))
        .filter(Product.id == product_id, Product.status == ProductStatus.ON)
        .first()
    )


def get_categories(db: Session):
    """分类树（两级）。"""
    categories = db.query(Category).order_by(Category.sort).all()
    root = [c for c in categories if c.parent_id is None]
    for r in root:
        r.children = [c for c in categories if c.parent_id == r.id]
    return root


def search_products(db: Session, keyword: str, limit: int = 5):
    """供 AI 客服使用的轻量商品检索（仅上架）。"""
    query = (
        db.query(Product)
        .options(selectinload(Product.skus))
        .filter(Product.status == ProductStatus.ON)
    )
    query = query.filter(
        or_(
            Product.name.ilike(f"%{keyword}%"),
            Product.description.ilike(f"%{keyword}%"),
        )
    )
    return query.order_by(Product.sales.desc()).limit(limit).all()


# --- Admin methods ---


def admin_get_products(db: Session, page: int = 1, page_size: int = 20):
    """管理端商品列表（含下架）。"""
    query = (
        db.query(Product)
        .options(selectinload(Product.skus))
        .order_by(Product.created_at.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def admin_create_product(db: Session, data: dict) -> Product:
    product = Product(
        name=data["name"],
        description=data.get("description"),
        price=data["price"],
        stock=data.get("stock") or 0,
        images=data.get("images") or [],
        category_id=data.get("category_id"),
        status=ProductStatus(data.get("status", "on")),
    )
    db.add(product)
    db.flush()
    _apply_skus(product, data.get("skus"))
    _ensure_default_sku(product)
    _sync_product_aggregates(product)
    db.commit()
    db.refresh(product)
    return product


def admin_update_product(db: Session, product_id: int, data: dict) -> Optional[Product]:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return None

    skus_data = data.pop("skus", None)
    for key, value in data.items():
        if value is not None:
            if key == "status":
                value = ProductStatus(value)
            setattr(product, key, value)

    if skus_data is not None:
        from app.models.cart import CartItem
        from app.models.order import OrderItem

        referenced = (
            db.query(OrderItem.id).filter(OrderItem.product_id == product.id).first()
        ) or (
            db.query(CartItem.id).filter(CartItem.product_id == product.id).first()
        )
        if referenced:
            payload_ids = {s.get("id") for s in skus_data}
            existing_ids = {s.id for s in product.skus}
            adding_new = any(not s.get("id") for s in skus_data)
            removing_old = bool(existing_ids - payload_ids)
            if adding_new or removing_old:
                raise HTTPException(
                    status_code=400,
                    detail="商品已有购物车/订单记录，只能编辑现有 SKU 的价格与库存，不能新增/删除 SKU",
                )
        _apply_skus(product, skus_data, allow_remove=not referenced)
    db.commit()
    db.refresh(product)
    return product


def admin_delete_product(db: Session, product_id: int) -> bool:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return False
    db.delete(product)
    db.commit()
    return True


def admin_get_all_categories(db: Session):
    return db.query(Category).order_by(Category.sort).all()


def admin_create_category(db: Session, data: dict) -> Category:
    category = Category(**data)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def admin_update_category(db: Session, category_id: int, data: dict) -> Optional[Category]:
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        return None
    for key, value in data.items():
        if value is not None:
            setattr(category, key, value)
    db.commit()
    db.refresh(category)
    return category


def admin_delete_category(db: Session, category_id: int) -> bool:
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        return False
    db.delete(category)
    db.commit()
    return True
