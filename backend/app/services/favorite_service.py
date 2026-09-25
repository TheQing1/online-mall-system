from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.models.content import Favorite
from app.models.product import Product, ProductStatus
from fastapi import HTTPException


def is_favorited(db: Session, user, product_id: int) -> bool:
    return (
        db.query(Favorite)
        .filter(
            Favorite.user_id == user.id,
            Favorite.product_id == product_id,
        )
        .first()
        is not None
    )


def add_favorite(db: Session, user, product_id: int) -> Favorite:
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.status == ProductStatus.ON)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")
    exists = (
        db.query(Favorite)
        .filter(
            Favorite.user_id == user.id,
            Favorite.product_id == product_id,
        )
        .first()
    )
    if exists:
        return exists
    favorite = Favorite(user_id=user.id, product_id=product_id)
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return favorite


def remove_favorite(db: Session, user, product_id: int) -> bool:
    favorite = (
        db.query(Favorite)
        .filter(
            Favorite.user_id == user.id,
            Favorite.product_id == product_id,
        )
        .first()
    )
    if not favorite:
        return False
    db.delete(favorite)
    db.commit()
    return True


def get_favorite_products(db: Session, user, page: int = 1, page_size: int = 20):
    query = (
        db.query(Product)
        .join(Favorite, Favorite.product_id == Product.id)
        .options(selectinload(Product.skus), selectinload(Product.category))
        .filter(
            Favorite.user_id == user.id,
            Product.status == ProductStatus.ON,
        )
        .order_by(Favorite.created_at.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    for item in items:
        if item.category:
            item.category_name = item.category.name
    return {"items": items, "total": total, "page": page, "page_size": page_size}
