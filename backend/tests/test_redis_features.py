"""需要真实 Redis 的用例：缓存、限流、分布式锁。

本地/CI 没有 Redis 时整个模块自动 skip（与 ``test_mysql_integration.py`` 同一套路）。

    REDIS_URL=redis://127.0.0.1:6379/9 pytest -m redis -v

默认用 db 9 并在每个用例前后 flushdb，避免污染开发用的数据。
"""

import threading

import pytest

from app.core import cache, locks
from app.core.cache import cache_delete_prefix, cache_get, cache_set, get_redis
from app.core.config import settings
from app.models.order import Order, OrderStatus

from tests.conftest import auth_header, create_address, create_product

# redis_db 夹具在 conftest 里，这里所有用例都依赖它（包括间接依赖 API 的那些）
pytestmark = [pytest.mark.redis, pytest.mark.usefixtures("redis_db")]


# --- 缓存 ---


def test_cache_roundtrip_and_prefix_delete():
    cache_set("product:detail:1", {"id": 1, "price": "9.90"}, ttl=60)
    cache_set("product:list:aaa", {"items": []}, ttl=60)
    cache_set("product:list:bbb", {"items": []}, ttl=60)

    assert cache_get("product:detail:1") == {"id": 1, "price": "9.90"}

    # 按前缀清理：列表的组合太多，只能整体清
    assert cache_delete_prefix("product:list:") == 2
    assert cache_get("product:list:aaa") is None
    # 详情不受影响
    assert cache_get("product:detail:1") is not None


def test_cache_get_returns_none_when_redis_is_down(monkeypatch):
    """Redis 挂了不能把业务带崩：读返回未命中、写静默丢弃。"""
    cache.reset_client()
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1/0")
    try:
        assert get_redis() is None
        assert cache_get("anything") is None
        cache_set("anything", {"a": 1}, ttl=60)  # 不应抛异常
        assert cache_delete_prefix("anything") == 0
    finally:
        cache.reset_client()


def test_product_detail_is_cached_and_invalidated_on_update(client, db, admin):
    """写路径必须清缓存，否则改完价格用户还是看到旧的。"""
    product = create_product(db, name="缓存商品", skus=[("S", {}, 100, 5)])

    first = client.get(f"/api/v1/products/{product.id}")
    assert first.status_code == 200
    assert get_redis().exists(f"product:detail:{product.id}")

    # 改价：详情与列表缓存都要失效
    headers = auth_header(client, "admin_test", "admin123")
    res = client.put(
        f"/api/v1/admin/products/{product.id}",
        json={"price": 88},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert not get_redis().exists(f"product:detail:{product.id}")

    again = client.get(f"/api/v1/products/{product.id}")
    assert again.status_code == 200


# --- 限流 ---


def test_login_is_rate_limited(client):
    """撞库防护：同一来源连续失败超过阈值后返回 429。"""
    limit = settings.rate_limit_login
    statuses = []
    for _ in range(limit + 1):
        res = client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "wrong-password"},
        )
        statuses.append(res.status_code)

    assert statuses[:limit] == [401] * limit
    assert statuses[-1] == 429


def test_rate_limited_response_tells_client_when_to_retry(client):
    limit = settings.rate_limit_login
    for _ in range(limit + 1):
        res = client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "wrong-password"},
        )

    assert res.status_code == 429
    assert res.headers.get("Retry-After")
    assert "秒后" in res.json()["detail"]


def test_global_api_limit_covers_every_endpoint(client, monkeypatch):
    """全站兜底配额：任何业务接口都会被计数（这里拿最普通的商品列表验）。"""
    monkeypatch.setattr(settings, "rate_limit_api", 3)

    statuses = [client.get("/api/v1/products").status_code for _ in range(4)]

    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 429


def test_global_limit_counts_across_different_endpoints(client, monkeypatch):
    """配额是「按身份」的总量，不是「每个接口各一份」——否则绕一绕就绕开了。"""
    monkeypatch.setattr(settings, "rate_limit_api", 2)

    first = client.get("/api/v1/products").status_code
    second = client.get("/api/v1/banners").status_code
    third = client.get("/api/v1/products/categories").status_code

    assert (first, second) == (200, 200)
    assert third == 429


def test_zero_quota_disables_the_limit(client, monkeypatch):
    """配额配 0 = 关闭。压测时必须能关，否则量到的是限流器而不是业务。"""
    monkeypatch.setattr(settings, "rate_limit_api", 0)

    assert all(client.get("/api/v1/products").status_code == 200 for _ in range(12))


# --- 分布式锁 ---


def test_redis_lock_is_mutually_exclusive():
    """同一把锁同时只能被一个持有者拿到。"""
    acquired_in_background = []

    with locks.redis_lock("unit-test-lock", ttl_seconds=10) as first:
        assert first.acquired and not first.degraded

        def try_acquire():
            with locks.redis_lock("unit-test-lock", ttl_seconds=10) as second:
                acquired_in_background.append(second.acquired)

        thread = threading.Thread(target=try_acquire)
        thread.start()
        thread.join(timeout=5)

    assert acquired_in_background == [False]

    # 释放之后应该能重新拿到
    with locks.redis_lock("unit-test-lock", ttl_seconds=10) as again:
        assert again.acquired


def test_expired_order_task_skips_when_another_replica_holds_the_lock(
    client, db, user, session_factory, monkeypatch
):
    """多副本部署时，同一轮关单只能有一个副本真正执行。"""
    from app.core import tasks

    # 定时任务自己开 Session（生产里是 SessionLocal），测试里指向同一个 SQLite
    monkeypatch.setattr(tasks, "SessionLocal", session_factory)

    product = create_product(db, name="待关单商品", skus=[("S", {}, 10, 3)])
    address = create_address(db, user)
    headers = auth_header(client, "buyer", "user123")
    client.post(
        "/api/v1/cart/items",
        json={"product_id": product.id, "sku_id": product.skus[0].id, "quantity": 1},
        headers=headers,
    )
    client.post("/api/v1/orders", json={"address_id": address.id}, headers=headers)

    # 把订单改成「早已超时」
    order = db.query(Order).first()
    order.created_at = order.created_at.replace(year=2000)
    db.commit()

    # 另一个副本持锁时，本轮应直接跳过
    with locks.redis_lock("cancel_expired_orders", ttl_seconds=10) as handle:
        assert handle.acquired
        assert tasks._cancel_expired_orders_once() == 0
    db.expire_all()
    assert db.query(Order).first().status == OrderStatus.PENDING_PAY

    # 锁释放后，同一轮任务才会真正关单
    assert tasks._cancel_expired_orders_once() == 1
    db.expire_all()
    assert db.query(Order).first().status == OrderStatus.CANCELLED
