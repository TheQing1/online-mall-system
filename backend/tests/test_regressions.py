"""针对审计发现问题的回归测试。

每个用例都对应一个真实修复过的缺陷，注释里写明了修复前的行为，
这样以后回归时能看懂「为什么要有这个断言」。
"""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import event

from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product, ProductStatus
from app.models.sku import ProductSku
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.services import order_service

from tests.conftest import auth_header, create_address, create_product


def _stock_of(db, sku_id):
    return db.query(ProductSku).filter(ProductSku.id == sku_id).first().stock


def _buy(client, db, headers, product, address, quantity=1, sku_id=None):
    payload = {"product_id": product.id, "quantity": quantity}
    if sku_id is not None:
        payload["sku_id"] = sku_id
    res = client.post("/api/v1/cart/items", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    order = client.post(
        "/api/v1/orders", json={"address_id": address.id}, headers=headers
    )
    assert order.status_code == 200, order.text
    return order.json()


# --- 购物车：累加后必须仍然满足库存 ---


def test_cart_rejects_cumulative_quantity_over_stock(client, db, user):
    """修复前只校验本次加购数量：stock=3 时加 2 再加 2 会得到 4 件。"""
    product = create_product(db, skus=[("默认规格", {}, 100, 3)])
    headers = auth_header(client, "buyer", "user123")
    sku = db.query(ProductSku).filter(ProductSku.product_id == product.id).first()

    first = client.post(
        "/api/v1/cart/items",
        json={"product_id": product.id, "quantity": 2},
        headers=headers,
    )
    assert first.status_code == 200
    assert first.json()["items"][0]["quantity"] == 2

    second = client.post(
        "/api/v1/cart/items",
        json={"product_id": product.id, "quantity": 2},
        headers=headers,
    )
    assert second.status_code == 400, second.text
    assert "库存不足" in second.json()["detail"]

    # 购物车保持原样，没有被写成 4
    cart = client.get("/api/v1/cart", headers=headers).json()
    assert cart["items"][0]["quantity"] == 2
    assert cart["items"][0]["sku_id"] == sku.id


def test_cart_allows_exactly_remaining_stock(client, db, user):
    product = create_product(db, skus=[("默认规格", {}, 100, 3)])
    headers = auth_header(client, "buyer", "user123")

    client.post(
        "/api/v1/cart/items",
        json={"product_id": product.id, "quantity": 2},
        headers=headers,
    )
    res = client.post(
        "/api/v1/cart/items",
        json={"product_id": product.id, "quantity": 1},
        headers=headers,
    )

    assert res.status_code == 200, res.text
    assert res.json()["items"][0]["quantity"] == 3


def test_cart_total_count_excludes_off_shelf_items(client, db, user):
    """修复前 total_count 统计了全部购物车行，下架商品也在内，与返回的 items 不一致。"""
    on_shelf = create_product(db, name="在售商品", skus=[("默认", {}, 10, 5)])
    off_shelf = create_product(db, name="下架商品", skus=[("默认", {}, 10, 5)])
    headers = auth_header(client, "buyer", "user123")

    client.post(
        "/api/v1/cart/items",
        json={"product_id": on_shelf.id, "quantity": 1},
        headers=headers,
    )
    client.post(
        "/api/v1/cart/items",
        json={"product_id": off_shelf.id, "quantity": 2},
        headers=headers,
    )

    off_shelf.status = ProductStatus.OFF
    db.commit()

    cart = client.get("/api/v1/cart", headers=headers).json()

    assert len(cart["items"]) == 1
    assert cart["total_count"] == 1


# --- 订单：原子状态流转 ---


def test_double_pay_is_rejected_and_sales_counted_once(client, db, user):
    product = create_product(db, skus=[("默认规格", {}, 100, 10)])
    headers = auth_header(client, "buyer", "user123")
    address = create_address(db, user)
    order = _buy(client, db, headers, product, address, quantity=2)

    first = client.post(f"/api/v1/orders/{order['id']}/pay", headers=headers)
    second = client.post(f"/api/v1/orders/{order['id']}/pay", headers=headers)

    assert first.status_code == 200, first.text
    assert second.status_code == 400, second.text

    db.expire_all()
    assert db.query(Product).filter(Product.id == product.id).first().sales == 2


def test_cannot_refund_a_pending_order(client, db, user):
    product = create_product(db, skus=[("默认规格", {}, 100, 10)])
    headers = auth_header(client, "buyer", "user123")
    address = create_address(db, user)
    order = _buy(client, db, headers, product, address)

    res = client.post(
        f"/api/v1/orders/{order['id']}/refund",
        json={"reason": "不想要了"},
        headers=headers,
    )

    assert res.status_code == 400, res.text


def test_refund_approval_restores_sku_stock_and_sales(client, db, user, admin):
    """修复前的用例只断言了商品聚合库存，SKU 维度从未被验证。"""
    product = create_product(db, skus=[("默认规格", {}, 100, 10)])
    sku = db.query(ProductSku).filter(ProductSku.product_id == product.id).first()
    headers = auth_header(client, "buyer", "user123")
    admin_headers = auth_header(client, "admin_test", "admin123")
    address = create_address(db, user)

    order = _buy(client, db, headers, product, address, quantity=3)
    client.post(f"/api/v1/orders/{order['id']}/pay", headers=headers)
    customer = client.get(f"/api/v1/orders/{order['id']}", headers=headers).json()
    assert customer["status"] == "paid"

    res = client.post(
        f"/api/v1/orders/{order['id']}/refund",
        json={"reason": "尺码不合适"},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    review = client.post(
        f"/api/v1/admin/orders/{order['id']}/refund/review",
        json={"approve": True, "note": "同意"},
        headers=admin_headers,
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "refunded"

    db.expire_all()
    assert _stock_of(db, sku.id) == 10
    assert db.query(Product).filter(Product.id == product.id).first().sales == 0


# --- 超时自动关单 ---


def test_auto_cancel_restores_stock_and_is_idempotent(client, db, user):
    product = create_product(db, skus=[("默认规格", {}, 100, 5)])
    sku = db.query(ProductSku).filter(ProductSku.product_id == product.id).first()
    headers = auth_header(client, "buyer", "user123")
    address = create_address(db, user)

    order = _buy(client, db, headers, product, address, quantity=2)
    assert _stock_of(db, sku.id) == 3

    # 把创建时间改到超时之前
    row = db.query(Order).filter(Order.id == order["id"]).first()
    row.created_at = datetime.now() - timedelta(minutes=120)
    db.commit()

    assert order_service.auto_cancel_expired_orders(db) == 1
    db.expire_all()
    assert db.query(Order).filter(Order.id == order["id"]).first().status == (
        OrderStatus.CANCELLED
    )
    assert _stock_of(db, sku.id) == 5

    # 再跑一次不应重复回补库存
    assert order_service.auto_cancel_expired_orders(db) == 0
    db.expire_all()
    assert _stock_of(db, sku.id) == 5


def test_auto_cancel_does_not_touch_paid_orders(client, db, user):
    """修复前是先查后改，并发下可能把已支付订单改成已取消。"""
    product = create_product(db, skus=[("默认规格", {}, 100, 5)])
    sku = db.query(ProductSku).filter(ProductSku.product_id == product.id).first()
    headers = auth_header(client, "buyer", "user123")
    address = create_address(db, user)

    order = _buy(client, db, headers, product, address, quantity=1)
    client.post(f"/api/v1/orders/{order['id']}/pay", headers=headers)

    row = db.query(Order).filter(Order.id == order["id"]).first()
    row.created_at = datetime.now() - timedelta(minutes=120)
    db.commit()

    assert order_service.auto_cancel_expired_orders(db) == 0
    db.expire_all()
    assert db.query(Order).filter(Order.id == order["id"]).first().status == (
        OrderStatus.PAID
    )
    assert _stock_of(db, sku.id) == 4


# --- 管理端用户开关 ---


def test_admin_cannot_disable_self(client, db, admin):
    headers = auth_header(client, "admin_test", "admin123")

    res = client.put(
        f"/api/v1/admin/users/{admin.id}/toggle-active", headers=headers
    )

    assert res.status_code == 400, res.text
    db.expire_all()
    assert db.query(User).filter(User.id == admin.id).first().is_active is True


def test_cannot_disable_last_active_admin(client, db, admin):
    """修复前可以把最后一个管理员禁用，导致后台彻底进不去。"""
    headers = auth_header(client, "admin_test", "admin123")
    other_admin = User(
        username="admin_two",
        password_hash=hash_password("admin123"),
        role=UserRole.ADMIN,
    )
    db.add(other_admin)
    db.commit()
    db.refresh(other_admin)

    # 先禁用第二个管理员（此时还有 admin_test 在启用状态，允许）
    ok = client.put(
        f"/api/v1/admin/users/{other_admin.id}/toggle-active", headers=headers
    )
    assert ok.status_code == 200, ok.text

    # 再想把 admin_test 自己禁用 —— 自己禁用被更早的规则挡住
    denied = client.put(
        f"/api/v1/admin/users/{admin.id}/toggle-active", headers=headers
    )
    assert denied.status_code == 400


def test_admin_can_disable_normal_user(client, db, admin, user):
    headers = auth_header(client, "admin_test", "admin123")

    res = client.put(
        f"/api/v1/admin/users/{user.id}/toggle-active", headers=headers
    )

    assert res.status_code == 200, res.text
    db.expire_all()
    assert db.query(User).filter(User.id == user.id).first().is_active is False


# --- 删除商品 ---


def test_cannot_delete_product_with_order_history(client, db, user, admin):
    """修复前 SQLite 下静默删除并留下孤儿订单项，MySQL 下则是外键 500。"""
    product = create_product(db, name="已售商品", skus=[("默认规格", {}, 100, 5)])
    headers = auth_header(client, "buyer", "user123")
    admin_headers = auth_header(client, "admin_test", "admin123")
    address = create_address(db, user)
    _buy(client, db, headers, product, address)

    res = client.delete(
        f"/api/v1/admin/products/{product.id}", headers=admin_headers
    )

    assert res.status_code == 400, res.text
    assert db.query(Product).filter(Product.id == product.id).first() is not None


def test_delete_product_clears_cart_and_favorites(client, db, user, admin):
    product = create_product(db, name="未售商品", skus=[("默认规格", {}, 100, 5)])
    headers = auth_header(client, "buyer", "user123")
    admin_headers = auth_header(client, "admin_test", "admin123")

    client.post(
        "/api/v1/cart/items",
        json={"product_id": product.id, "quantity": 1},
        headers=headers,
    )
    client.post(f"/api/v1/users/favorites/{product.id}", headers=headers)

    res = client.delete(
        f"/api/v1/admin/products/{product.id}", headers=admin_headers
    )

    assert res.status_code == 200, res.text
    assert db.query(Product).filter(Product.id == product.id).first() is None


# --- 用户列表契约 ---


def test_admin_user_list_exposes_is_active(client, db, admin, user):
    """UserOut 之前没有 is_active，后台的启用/禁用开关读到的永远是 undefined。"""
    headers = auth_header(client, "admin_test", "admin123")

    res = client.get("/api/v1/admin/users", headers=headers)

    assert res.status_code == 200, res.text
    first = res.json()["items"][0]
    assert "is_active" in first
    assert isinstance(first["is_active"], bool)


# --- 订单列表：订单项必须批量取 ---


def _seed_order(db, user, index):
    """直接落库造一笔带订单项的订单，供只关心 SQL 条数的用例使用。"""
    product = create_product(db, name=f"列表商品{index}", skus=[("S", {}, 10, 3)])
    sku = product.skus[0]
    order = Order(
        user_id=user.id,
        order_no=f"20260927{index:012d}",
        total_amount=Decimal("10.00"),
        status=OrderStatus.PENDING_PAY,
        address_snapshot={"receiver": "张三"},
    )
    db.add(order)
    db.flush()
    db.add(
        OrderItem(
            order_id=order.id,
            product_id=product.id,
            sku_id=sku.id,
            sku_name=sku.name,
            sku_spec={},
            product_name=product.name,
            price=sku.price,
            quantity=1,
        )
    )
    db.commit()
    return order


def _order_list_query_count(client, db, headers):
    """请求订单列表，返回 (响应体, 实际执行的 SQL 条数)。"""
    bind = db.get_bind()
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    # 先让 session 里的对象全部过期。否则对象从标识映射直接命中、懒加载不发 SQL，
    # 这个用例就变成「怎么改都能过」。
    db.expire_all()
    event.listen(bind, "before_cursor_execute", record)
    try:
        res = client.get("/api/v1/orders", headers=headers)
    finally:
        event.remove(bind, "before_cursor_execute", record)
    assert res.status_code == 200, res.text
    return res.json(), statements


def test_order_list_does_not_trigger_n_plus_one(client, db, user):
    """修复前列表查询没有 eager load，而 OrderOut 带 items 字段，
    每页 N 条订单会额外触发 N 次懒加载（N+1）。

    断言的是「SQL 条数不随订单数量增长」而不是写死一个数字：
    这样以后改字段、换实现都不会让用例变脆，同时足以抓住真正的 N+1。
    """
    headers = auth_header(client, "buyer", "user123")
    _seed_order(db, user, 1)
    _, single = _order_list_query_count(client, db, headers)

    for index in range(2, 7):
        _seed_order(db, user, index)
    payload, six = _order_list_query_count(client, db, headers)

    assert payload["total"] == 6
    assert len(payload["items"][0]["items"]) == 1
    assert len(six) == len(single), (single, six)
