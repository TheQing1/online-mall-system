from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app.models.cart import CartItem
from app.models.product import Product, ProductStatus
from app.models.sku import ProductSku


def _get_default_sku(db: Session, product_id: int) -> Optional[ProductSku]:
    return (
        db.query(ProductSku)
        .filter(ProductSku.product_id == product_id)
        .order_by(ProductSku.id)
        .first()
    )


def resolve_sku(db: Session, product_id: int, sku_id: Optional[int]) -> ProductSku:
    """校验商品可用并解析 SKU（未指定时取默认 SKU）。"""
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.status == ProductStatus.ON)
        .first()
    )
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在或已下架"
        )
    sku = (
        db.query(ProductSku).filter(ProductSku.id == sku_id).first()
        if sku_id
        else None
    )
    if sku is None:
        sku = _get_default_sku(db, product_id)
    if sku is None or sku.product_id != product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="SKU 不存在或不属于该商品"
        )
    return sku


def get_cart_items(db: Session, user) -> list[CartItem]:
    """购物车 ORM 列表（内部/下单使用）。"""
    return (
        db.query(CartItem)
        .options(joinedload(CartItem.product), joinedload(CartItem.sku))
        .filter(CartItem.user_id == user.id)
        .order_by(CartItem.created_at.desc())
        .all()
    )


def calculate_total(items: list[CartItem]) -> Decimal:
    """按 SKU 单价计算购物车合计（仅上架商品）。"""
    total = Decimal("0")
    for item in items:
        if item.sku and item.product and item.product.status == ProductStatus.ON:
            total += item.sku.price * item.quantity
    return total


def get_cart(db: Session, user) -> dict:
    """购物车接口返回结构。"""
    items = get_cart_items(db, user)
    total_amount = calculate_total(items)
    payload_items = []
    for item in items:
        if not item.product or not item.sku:
            continue
        if item.product.status != ProductStatus.ON:
            continue
        image = item.product.images[0] if item.product.images else ""
        payload_items.append(
            {
                "id": item.id,
                "product_id": item.product_id,
                "sku_id": item.sku_id,
                "quantity": item.quantity,
                "sku_name": item.sku.name,
                "sku_spec": item.sku.specs or {},
                "unit_price": item.sku.price,
                "product": {
                    "id": item.product.id,
                    "name": item.product.name,
                    "image": image,
                },
            }
        )
    return {
        "items": payload_items,
        "total_count": sum(i.quantity for i in items),
        "total_amount": total_amount,
    }


def add_cart_item(
    db: Session, user, product_id: int, quantity: int, sku_id: Optional[int] = None
) -> CartItem:
    sku = resolve_sku(db, product_id, sku_id)
    if sku.stock < quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="库存不足")

    item = (
        db.query(CartItem)
        .filter(CartItem.user_id == user.id, CartItem.sku_id == sku.id)
        .first()
    )
    if item:
        item.quantity += quantity
    else:
        item = CartItem(
            user_id=user.id, product_id=product_id, sku_id=sku.id, quantity=quantity
        )
        db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_cart_item(db: Session, item_id: int, user, quantity: int) -> CartItem:
    item = (
        db.query(CartItem)
        .filter(CartItem.id == item_id, CartItem.user_id == user.id)
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="购物车项不存在"
        )
    if item.sku and item.sku.stock < quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="库存不足")
    item.quantity = quantity
    db.commit()
    db.refresh(item)
    return item


def delete_cart_item(db: Session, item_id: int, user) -> bool:
    item = (
        db.query(CartItem)
        .filter(CartItem.id == item_id, CartItem.user_id == user.id)
        .first()
    )
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


def clear_cart(db: Session, user):
    db.query(CartItem).filter(CartItem.user_id == user.id).delete()
    db.commit()
