from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.models.product import Product, Category, ProductStatus

def get_products(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    category_id: Optional[int] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    """公开商品列表（仅上架商品），支持搜索、分类筛选、排序"""
    query = db.query(Product).filter(Product.status == ProductStatus.ON)

    if keyword:
        query = query.filter(
            or_(
                Product.name.ilike(f"%{keyword}%"),
                Product.description.ilike(f"%{keyword}%")
            )
        )

    if category_id:
        # 包含子分类
        sub_ids = [category_id]
        sub_categories = db.query(Category).filter(Category.parent_id == category_id).all()
        sub_ids.extend([c.id for c in sub_categories])
        query = query.filter(Product.category_id.in_(sub_ids))

    # 排序（白名单校验）
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

    # 附加 category_name
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
    """商品详情（仅上架）"""
    return db.query(Product).filter(
        Product.id == product_id,
        Product.status == ProductStatus.ON
    ).first()

def get_categories(db: Session):
    """分类树"""
    categories = db.query(Category).order_by(Category.sort).all()
    root = [c for c in categories if c.parent_id is None]
    for r in root:
        r.children = [c for c in categories if c.parent_id == r.id]
    return root

# --- Admin methods ---

def admin_get_products(db: Session, page: int = 1, page_size: int = 20):
    """管理端商品列表（包含下架商品）"""
    query = db.query(Product).order_by(Product.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}

def admin_create_product(db: Session, data: dict) -> Product:
    """管理员创建商品"""
    product = Product(**data)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

def admin_update_product(db: Session, product_id: int, data: dict) -> Optional[Product]:
    """管理员更新商品"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return None
    for key, value in data.items():
        if value is not None:
            setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return product

def admin_delete_product(db: Session, product_id: int) -> bool:
    """管理员删除商品"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return False
    db.delete(product)
    db.commit()
    return True

# --- Category admin methods ---

def admin_get_all_categories(db: Session):
    """管理端分类列表（扁平）"""
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
