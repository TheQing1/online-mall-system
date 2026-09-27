import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import update
from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product, ProductStatus
from app.models.sku import ProductSku
from app.models.user import Address
from app.services import cart_service


def _deduct_stock(db: Session, sku: ProductSku, quantity: int) -> bool:
    """原子扣减 SKU 与商品聚合库存；返回是否成功（防超卖）。"""
    sku_ok = db.execute(
        update(ProductSku)
        .where(ProductSku.id == sku.id, ProductSku.stock >= quantity)
        .values(stock=ProductSku.stock - quantity)
    ).rowcount
    if not sku_ok:
        return False
    product_ok = db.execute(
        update(Product)
        .where(Product.id == sku.product_id, Product.stock >= quantity)
        .values(stock=Product.stock - quantity)
    ).rowcount
    return bool(product_ok)


def _restore_stock(db: Session, order: Order):
    """取消/退款时回补库存。"""
    for item in order.items:
        db.execute(
            update(ProductSku)
            .where(ProductSku.id == item.sku_id)
            .values(stock=ProductSku.stock + item.quantity)
        )
        db.execute(
            update(Product)
            .where(Product.id == item.product_id)
            .values(stock=Product.stock + item.quantity)
        )


def _increase_sales(db: Session, order: Order):
    """支付成功时累加销量。"""
    for item in order.items:
        db.execute(
            update(Product)
            .where(Product.id == item.product_id)
            .values(sales=Product.sales + item.quantity)
        )


def _decrease_sales(db: Session, order: Order):
    """退款成功时回退销量。"""
    for item in order.items:
        db.execute(
            update(Product)
            .where(Product.id == item.product_id)
            .values(sales=Product.sales - item.quantity)
        )


def create_order(
    db: Session, user, address_id: int, remark: Optional[str] = None
) -> Order:
    try:
        address = (
            db.query(Address)
            .filter(Address.id == address_id, Address.user_id == user.id)
            .first()
        )
        if not address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在"
            )

        items = cart_service.get_cart_items(db, user)
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="购物车为空"
            )

        # 校验商品状态与库存，并原子扣减
        order_items_data = []
        for cart_item in items:
            product = (
                db.query(Product).filter(Product.id == cart_item.product_id).first()
            )
            if not product or product.status != ProductStatus.ON:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"商品「{cart_item.product.name}」已下架",
                )
            sku = cart_item.sku
            if not sku or not _deduct_stock(db, sku, cart_item.quantity):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"商品「{product.name}」库存不足",
                )
            order_items_data.append((product, sku, cart_item.quantity))

        order_no = datetime.now().strftime("%Y%m%d") + uuid.uuid4().hex[:12].upper()
        address_snapshot = {
            "receiver": address.receiver,
            "phone": address.phone,
            "province": address.province,
            "city": address.city,
            "district": address.district,
            "detail": address.detail,
        }

        total_amount = cart_service.calculate_total(items)
        order = Order(
            user_id=user.id,
            order_no=order_no,
            total_amount=total_amount,
            status=OrderStatus.PENDING_PAY,
            address_snapshot=address_snapshot,
            remark=remark,
        )
        db.add(order)
        db.flush()

        for product, sku, quantity in order_items_data:
            db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    sku_id=sku.id,
                    sku_name=sku.name,
                    sku_spec=sku.specs or {},
                    product_name=product.name,
                    product_image=product.images[0] if product.images else None,
                    price=sku.price,
                    quantity=quantity,
                )
            )

        cart_service.clear_cart(db, user, commit=False)
        db.commit()
        db.refresh(order)
        return order
    except Exception:
        db.rollback()
        raise


def _transition(
    db: Session, order_id: int, from_status: OrderStatus, to_status: OrderStatus, **values
) -> bool:
    """原子状态流转：只有当前仍处于 ``from_status`` 时才更新。

    先读状态再写（check-then-act）在并发下会出问题：两次支付请求可能都读到
    ``pending_pay``，于是销量被累加两次；自动关单任务也可能把刚刚支付成功的
    订单改成 ``cancelled``。这里用条件 UPDATE 的 rowcount 做乐观并发控制。
    """
    updated = db.execute(
        update(Order)
        .where(Order.id == order_id, Order.status == from_status)
        .values(status=to_status, **values)
        .execution_options(synchronize_session=False)
    ).rowcount
    return bool(updated)


def pay_order(db: Session, order_id: int, user) -> Order:
    """页面化模拟支付：由收银台页面发起，将待支付订单置为已支付。"""
    order = _get_user_order(db, order_id, user)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if not _transition(
        db, order.id, OrderStatus.PENDING_PAY, OrderStatus.PAID, paid_at=datetime.now()
    ):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="仅待支付订单可支付"
        )
    _increase_sales(db, order)
    db.commit()
    db.refresh(order)
    return order


def complete_order(db: Session, order_id: int, user) -> Order:
    """用户确认收货。"""
    order = _get_user_order(db, order_id, user)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if not _transition(db, order.id, OrderStatus.SHIPPED, OrderStatus.COMPLETED):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="仅已发货订单可确认收货"
        )
    db.commit()
    db.refresh(order)
    return order


def cancel_order(db: Session, order_id: int, user) -> Optional[Order]:
    order = _get_user_order(db, order_id, user)
    if not order:
        return None
    if not _transition(db, order.id, OrderStatus.PENDING_PAY, OrderStatus.CANCELLED):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="仅待支付订单可取消"
        )
    _restore_stock(db, order)
    db.commit()
    db.refresh(order)
    return order


def apply_refund(db: Session, order_id: int, user, reason: str) -> Order:
    order = _get_user_order(db, order_id, user)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if order.status not in (
        OrderStatus.PAID,
        OrderStatus.SHIPPED,
        OrderStatus.COMPLETED,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态不可申请退款"
        )
    if not _transition(
        db,
        order.id,
        order.status,
        OrderStatus.REFUNDING,
        refund_from_status=order.status.value,
        refund_reason=reason,
    ):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="订单状态已变更，请刷新后重试",
        )
    db.commit()
    db.refresh(order)
    return order


def _get_user_order(db: Session, order_id: int, user) -> Optional[Order]:
    return (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == user.id)
        .first()
    )


def get_user_orders(
    db: Session, user, page: int = 1, page_size: int = 10, status_filter=None
):
    # 订单项必须批量取：响应模型带 items，逐条懒加载的话一页 10 条订单
    # 会额外产生 10 条 SQL（N+1）。
    query = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
    )
    if status_filter:
        try:
            query = query.filter(Order.status == OrderStatus(status_filter))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="无效的订单状态"
            )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_order(db: Session, order_id: int, user) -> Optional[Order]:
    return (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == user.id)
        .first()
    )


# --- Admin methods ---


def admin_get_orders(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    order_no: Optional[str] = None,
):
    query = (
        db.query(Order)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )
    if status_filter:
        try:
            query = query.filter(Order.status == OrderStatus(status_filter))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="无效的订单状态"
            )
    if order_no:
        query = query.filter(Order.order_no.ilike(f"%{order_no}%"))
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


_ADMIN_ALLOWED_TRANSITIONS = {
    OrderStatus.PENDING_PAY: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.SHIPPED},
    OrderStatus.SHIPPED: {OrderStatus.COMPLETED},
}


def admin_update_order_status(
    db: Session, order_id: int, new_status: str
) -> Optional[Order]:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return None
    try:
        target = OrderStatus(new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="无效的订单状态"
        )

    allowed = _ADMIN_ALLOWED_TRANSITIONS.get(order.status)
    if not allowed or target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不允许从 {order.status.value} 流转到 {target.value}",
        )

    values = {}
    if target == OrderStatus.PAID:
        values["paid_at"] = datetime.now()

    if not _transition(db, order.id, order.status, target, **values):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="订单状态已被其他操作修改，请刷新后重试",
        )

    if target == OrderStatus.PAID:
        _increase_sales(db, order)
    elif target == OrderStatus.CANCELLED:
        _restore_stock(db, order)
    db.commit()
    db.refresh(order)
    return order


def admin_get_refund_orders(db: Session, page: int = 1, page_size: int = 20):
    query = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.status == OrderStatus.REFUNDING)
        .order_by(Order.created_at.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def admin_review_refund(
    db: Session, order_id: int, approve: bool, note: Optional[str] = None
) -> Optional[Order]:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return None
    if order.status != OrderStatus.REFUNDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="订单不在退款中"
        )

    try:
        target = (
            OrderStatus.REFUNDED
            if approve
            else OrderStatus(order.refund_from_status or "paid")
        )
    except ValueError:
        target = OrderStatus.PAID

    values = {"refund_note": note, "refund_from_status": None}
    if approve:
        values["refunded_at"] = datetime.now()

    if not _transition(db, order.id, OrderStatus.REFUNDING, target, **values):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="订单状态已变更，请刷新后重试",
        )

    if approve:
        _restore_stock(db, order)
        _decrease_sales(db, order)
    db.commit()
    db.refresh(order)
    return order


def auto_cancel_expired_orders(db: Session, expire_minutes: Optional[int] = None):
    """待支付超过时限自动关单并回补库存。返回取消数量。

    逐单做条件 UPDATE，避免和用户支付并发时把已支付订单改成 cancelled。
    """
    minutes = expire_minutes or settings.order_expire_minutes
    deadline = datetime.now() - timedelta(minutes=minutes)
    expired_ids = [
        row[0]
        for row in db.query(Order.id)
        .filter(
            Order.status == OrderStatus.PENDING_PAY,
            Order.created_at < deadline,
        )
        .all()
    ]

    cancelled = 0
    for order_id in expired_ids:
        if not _transition(
            db, order_id, OrderStatus.PENDING_PAY, OrderStatus.CANCELLED
        ):
            # 期间被支付或取消，跳过
            continue
        order = db.query(Order).filter(Order.id == order_id).first()
        _restore_stock(db, order)
        cancelled += 1
    if cancelled:
        db.commit()
    return cancelled


def admin_get_dashboard_stats(db: Session) -> dict:
    from sqlalchemy import func

    from app.models.user import User

    total_users = db.query(User).count()
    total_orders = db.query(Order).count()
    total_revenue = (
        db.query(Order)
        .filter(
            Order.status.in_(
                [OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.COMPLETED]
            )
        )
        .with_entities(func.sum(Order.total_amount))
        .scalar()
        or 0
    )
    total_products = db.query(Product).count()
    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "total_revenue": float(total_revenue),
        "total_products": total_products,
        "pending_refunds": (
            db.query(Order).filter(Order.status == OrderStatus.REFUNDING).count()
        ),
    }
