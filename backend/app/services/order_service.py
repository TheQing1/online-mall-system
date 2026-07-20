import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.order import Order, OrderItem, OrderStatus
from app.models.cart import CartItem
from app.models.product import Product, ProductStatus
from app.models.user import Address
from app.services import cart_service

def create_order(db: Session, user, address_id: int, remark: Optional[str] = None) -> Order:
    # 1. 验证地址
    address = db.query(Address).filter(
        Address.id == address_id, Address.user_id == user.id
    ).first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在")

    # 2. 获取购物车
    cart = cart_service.get_cart(db, user)
    if not cart["items"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="购物车为空")

    # 3. 检查库存
    for cart_item in cart["items"]:
        product = db.query(Product).filter(Product.id == cart_item.product_id).first()
        if not product or product.status != ProductStatus.ON:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"商品「{cart_item.product.name}」已下架")
        if product.stock < cart_item.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"商品「{product.name}」库存不足")

    # 4. 生成订单号
    order_no = datetime.now().strftime("%Y%m%d") + uuid.uuid4().hex[:12].upper()

    # 5. 快照地址
    address_snapshot = {
        "receiver": address.receiver, "phone": address.phone,
        "province": address.province, "city": address.city,
        "district": address.district, "detail": address.detail,
    }

    # 6. 创建订单
    order = Order(
        user_id=user.id,
        order_no=order_no,
        total_amount=cart["total_amount"],
        status=OrderStatus.PENDING_PAY,
        address_snapshot=address_snapshot,
        remark=remark,
    )
    db.add(order)
    db.flush()  # 获取 order.id

    # 7. 创建订单项 + 扣库存 + 增销量
    for cart_item in cart["items"]:
        product = db.query(Product).filter(Product.id == cart_item.product_id).first()
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name=product.name,
            product_image=product.images[0] if product.images else None,
            price=product.price,
            quantity=cart_item.quantity,
        )
        db.add(order_item)
        # 扣库存，增销量
        product.stock -= cart_item.quantity
        product.sales += cart_item.quantity

    # 8. 模拟支付成功
    order.status = OrderStatus.PAID

    # 9. 清空购物车
    cart_service.clear_cart(db, user)

    db.commit()
    db.refresh(order)
    return order

def get_user_orders(db: Session, user, page: int = 1, page_size: int = 10):
    query = db.query(Order).filter(Order.user_id == user.id).order_by(Order.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}

def get_order(db: Session, order_id: int, user) -> Optional[Order]:
    return db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()

def cancel_order(db: Session, order_id: int, user) -> Optional[Order]:
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order:
        return None
    if order.status != OrderStatus.PENDING_PAY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅待付款订单可取消")
    order.status = OrderStatus.CANCELLED
    # 恢复库存
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
            product.stock += item.quantity
    db.commit()
    db.refresh(order)
    return order

# --- Admin methods ---

def admin_get_orders(db: Session, page: int = 1, page_size: int = 20, status_filter: Optional[str] = None):
    query = db.query(Order).order_by(Order.created_at.desc())
    if status_filter:
        query = query.filter(Order.status == status_filter)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}

def admin_update_order_status(db: Session, order_id: int, new_status: str) -> Optional[Order]:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return None
    try:
        order.status = OrderStatus(new_status)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的订单状态")
    db.commit()
    db.refresh(order)
    return order

def admin_get_dashboard_stats(db: Session) -> dict:
    from app.models.user import User
    total_users = db.query(User).count()
    total_orders = db.query(Order).count()
    total_revenue = db.query(Order).filter(Order.status.in_([OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.COMPLETED])).with_entities(
        __import__('sqlalchemy').func.sum(Order.total_amount)
    ).scalar() or 0
    total_products = db.query(Product).count()
    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "total_revenue": float(total_revenue),
        "total_products": total_products,
    }
