from sqlalchemy.orm import Session, joinedload
from app.models.cart import CartItem
from app.models.product import Product, ProductStatus
from fastapi import HTTPException, status

def get_cart(db: Session, user) -> dict:
    items = (
        db.query(CartItem)
        .options(joinedload(CartItem.product))
        .filter(CartItem.user_id == user.id)
        .all()
    )
    total_amount = 0.0
    for item in items:
        if item.product and item.product.status == ProductStatus.ON:
            total_amount += float(item.product.price) * item.quantity

    return {
        "items": items,
        "total_count": sum(i.quantity for i in items),
        "total_amount": round(total_amount, 2),
    }

def add_cart_item(db: Session, user, product_id: int, quantity: int) -> CartItem:
    product = db.query(Product).filter(
        Product.id == product_id, Product.status == ProductStatus.ON
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在或已下架")
    if product.stock < quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="库存不足")

    item = db.query(CartItem).filter(
        CartItem.user_id == user.id, CartItem.product_id == product_id
    ).first()
    if item:
        item.quantity += quantity
    else:
        item = CartItem(user_id=user.id, product_id=product_id, quantity=quantity)
        db.add(item)
    db.commit()
    db.refresh(item)
    return item

def update_cart_item(db: Session, item_id: int, user, quantity: int) -> CartItem:
    item = db.query(CartItem).filter(
        CartItem.id == item_id, CartItem.user_id == user.id
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="购物车项不存在")
    item.quantity = quantity
    db.commit()
    db.refresh(item)
    return item

def delete_cart_item(db: Session, item_id: int, user) -> bool:
    item = db.query(CartItem).filter(
        CartItem.id == item_id, CartItem.user_id == user.id
    ).first()
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True

def clear_cart(db: Session, user):
    db.query(CartItem).filter(CartItem.user_id == user.id).delete()
    db.commit()
