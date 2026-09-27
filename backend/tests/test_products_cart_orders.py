from tests.conftest import auth_header, create_address, create_product


def test_product_list_and_detail(client, db, admin):
    create_product(db, "iPhone 15")
    create_product(db, "华为手机")

    res = client.get("/api/v1/products")
    assert res.status_code == 200
    assert res.json()["total"] == 2

    res = client.get("/api/v1/products", params={"keyword": "华为"})
    assert res.json()["total"] == 1

    pid = res.json()["items"][0]["id"]
    detail = client.get(f"/api/v1/products/{pid}")
    assert detail.status_code == 200
    assert len(detail.json()["skus"]) >= 1


def test_cart_sku_and_stock_limit(client, db, user):
    product = create_product(
        db,
        "多规格手机",
        skus=[("黑色 256GB", {"颜色": "黑色"}, 5999, 2), ("白色 256GB", {"颜色": "白色"}, 6199, 1)],
    )
    sku_black = product.skus[0]
    headers = auth_header(client, "buyer", "user123")

    res = client.post(
        "/api/v1/cart/items",
        json={"product_id": product.id, "sku_id": sku_black.id, "quantity": 1},
        headers=headers,
    )
    assert res.status_code == 200
    item = res.json()["items"][0]
    assert item["sku_id"] == sku_black.id
    assert str(item["unit_price"]) == "5999.00"

    # 库存不足应拒绝
    res = client.post(
        "/api/v1/cart/items",
        json={"product_id": product.id, "sku_id": sku_black.id, "quantity": 5},
        headers=headers,
    )
    assert res.status_code == 400

    cart = client.get("/api/v1/cart", headers=headers)
    assert cart.status_code == 200
    assert cart.json()["total_count"] == 1


def test_order_pay_cancel_refund_flow(client, db, user, admin):
    product = create_product(
        db,
        "交易商品",
        skus=[("标准版", {"版本": "标准"}, 199, 5)],
    )
    sku = product.skus[0]
    addr = create_address(db, user)
    headers = auth_header(client, "buyer", "user123")
    admin_headers = auth_header(client, "admin_test", "admin123")

    client.post(
        "/api/v1/cart/items",
        json={"product_id": product.id, "sku_id": sku.id, "quantity": 2},
        headers=headers,
    )
    res = client.post(
        "/api/v1/orders",
        json={"address_id": addr.id, "remark": "请尽快发货"},
        headers=headers,
    )
    assert res.status_code == 200
    order = res.json()
    assert order["status"] == "pending_pay"
    assert order["items"][0]["sku_name"] == "标准版"

    # 下单后扣库存，未支付不加销量
    client_orders = client.get("/api/v1/orders", headers=headers)
    assert client_orders.json()["total"] == 1

    # 支付
    paid = client.post(f"/api/v1/orders/{order['id']}/pay", headers=headers)
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"
    assert paid.json()["paid_at"]

    # 发货 → 确认收货
    shipped = client.put(
        f"/api/v1/admin/orders/{order['id']}/status",
        params={"status": "shipped"},
        headers=admin_headers,
    )
    assert shipped.status_code == 200
    completed = client.put(
        f"/api/v1/orders/{order['id']}/complete", headers=headers
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    # 退款申请 → 管理员同意 → 库存/销量回滚
    refunding = client.post(
        f"/api/v1/orders/{order['id']}/refund",
        json={"reason": "不想要了"},
        headers=headers,
    )
    assert refunding.status_code == 200
    assert refunding.json()["status"] == "refunding"

    refunded = client.post(
        f"/api/v1/admin/orders/{order['id']}/refund/review",
        json={"approve": True, "note": "同意"},
        headers=admin_headers,
    )
    assert refunded.status_code == 200
    assert refunded.json()["status"] == "refunded"

    product = db.query(type(product)).get(product.id)
    assert product.stock == 5
    assert product.sales == 0


def test_cancel_order_restores_stock(client, db, user):
    product = create_product(db, "可取消商品", skus=[("S", {}, 50, 3)])
    sku = product.skus[0]
    addr = create_address(db, user)
    headers = auth_header(client, "buyer", "user123")

    client.post(
        "/api/v1/cart/items",
        json={"product_id": product.id, "sku_id": sku.id, "quantity": 1},
        headers=headers,
    )
    order = client.post(
        "/api/v1/orders", json={"address_id": addr.id}, headers=headers
    ).json()
    client.put(f"/api/v1/orders/{order['id']}/cancel", headers=headers)

    db.refresh(product)
    assert product.stock == 3


def test_refund_reject_returns_to_original(client, db, user, admin):
    product = create_product(db, "驳回商品", skus=[("S", {}, 50, 3)])
    sku = product.skus[0]
    addr = create_address(db, user)
    headers = auth_header(client, "buyer", "user123")
    admin_headers = auth_header(client, "admin_test", "admin123")

    client.post(
        "/api/v1/cart/items",
        json={"product_id": product.id, "sku_id": sku.id, "quantity": 1},
        headers=headers,
    )
    order = client.post(
        "/api/v1/orders", json={"address_id": addr.id}, headers=headers
    ).json()
    client.post(f"/api/v1/orders/{order['id']}/pay", headers=headers)

    client.post(
        f"/api/v1/orders/{order['id']}/refund",
        json={"reason": "测试"},
        headers=headers,
    )
    res = client.post(
        f"/api/v1/admin/orders/{order['id']}/refund/review",
        json={"approve": False, "note": "不符合政策"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "paid"
    assert res.json()["refund_note"] == "不符合政策"


def test_page_size_is_bounded(client):
    """分页上限写死在 Query(le=...)：超过上限要报 422，而不是让客户端
    用一个巨大的 page_size 把整张表拉走。"""
    assert client.get("/api/v1/products", params={"page_size": 101}).status_code == 422
    assert client.get("/api/v1/products", params={"page_size": 0}).status_code == 422
    assert client.get("/api/v1/products", params={"page": 0}).status_code == 422


def test_cart_rejects_sku_belonging_to_another_product(client, db, user):
    """sku_id 必须属于所加购的商品：否则可以把 A 商品的低价 SKU 挂到
    B 商品上（下单是按 SKU 价格算钱的）。"""
    cheap = create_product(db, "便宜商品", skus=[("低价版", {}, 1, 10)])
    expensive = create_product(db, "昂贵商品", skus=[("高价版", {}, 999, 10)])
    headers = auth_header(client, "buyer", "user123")

    res = client.post(
        "/api/v1/cart/items",
        json={
            "product_id": expensive.id,
            "sku_id": cheap.skus[0].id,
            "quantity": 1,
        },
        headers=headers,
    )

    assert res.status_code == 400, res.text
