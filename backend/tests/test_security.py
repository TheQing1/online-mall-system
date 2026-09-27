"""鉴权与越权（IDOR）回归测试。

这些用例对应项目审计中发现的问题：
- ``api/users.py`` 用到了 ``status`` 却没 import，访问不存在的地址会 500；
- ``api/ai_chat.py`` 的会话接口没有归属校验，任何拿到 session_id 的人都能读/删；
- 管理端接口缺少「普通用户访问应被拒绝」的断言。
"""

import uuid

from app.models.chat import ChatMessage, ChatSession
from app.models.user import User, UserRole
from app.core.security import create_access_token, hash_password

from tests.conftest import create_address, create_product


def _login(client, username, password):
    res = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _make_user(db, username, role=UserRole.USER):
    user = User(
        username=username, password_hash=hash_password("pass1234"), role=role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_session(db, owner):
    session = ChatSession(
        id=str(uuid.uuid4()), user_id=owner.id if owner else None, title="测试会话"
    )
    db.add(session)
    db.flush()
    db.add(ChatMessage(session_id=session.id, role="user", content="我的私密问题"))
    db.add(ChatMessage(session_id=session.id, role="assistant", content="私密回答"))
    db.commit()
    return session


# --- 地址接口曾经因为缺少 status import 抛 NameError（500） ---


def test_update_missing_address_returns_404(client, db):
    _make_user(db, "addr_user")
    headers = _login(client, "addr_user", "pass1234")

    res = client.put(
        "/api/v1/users/addresses/999999",
        headers=headers,
        json={
            "receiver": "张三",
            "phone": "13800138000",
            "province": "广东省",
            "city": "深圳市",
            "district": "南山区",
            "detail": "科技园 1 号",
        },
    )

    assert res.status_code == 404, res.text


def test_delete_missing_address_returns_404(client, db):
    _make_user(db, "addr_user2")
    headers = _login(client, "addr_user2", "pass1234")

    res = client.delete("/api/v1/users/addresses/999999", headers=headers)

    assert res.status_code == 404, res.text


# --- AI 会话归属 ---


def test_other_user_cannot_read_chat_messages(client, db):
    owner = _make_user(db, "chat_owner")
    _make_user(db, "chat_intruder")
    session = _make_session(db, owner)

    intruder_headers = _login(client, "chat_intruder", "pass1234")
    res = client.get(
        f"/api/v1/ai-chat/sessions/{session.id}/messages", headers=intruder_headers
    )

    assert res.status_code == 403, res.text


def test_other_user_cannot_delete_chat_session(client, db):
    owner = _make_user(db, "chat_owner2")
    _make_user(db, "chat_intruder2")
    session = _make_session(db, owner)

    intruder_headers = _login(client, "chat_intruder2", "pass1234")
    res = client.delete(
        f"/api/v1/ai-chat/sessions/{session.id}", headers=intruder_headers
    )

    assert res.status_code == 403, res.text
    # 会话与被拒绝前一样还在
    assert db.query(ChatSession).filter(ChatSession.id == session.id).first() is not None


def test_owner_can_read_own_chat_messages(client, db):
    owner = _make_user(db, "chat_self")
    session = _make_session(db, owner)

    headers = _login(client, "chat_self", "pass1234")
    res = client.get(
        f"/api/v1/ai-chat/sessions/{session.id}/messages", headers=headers
    )

    assert res.status_code == 200, res.text
    contents = [m["content"] for m in res.json()]
    assert contents == ["我的私密问题", "私密回答"]


def test_missing_chat_session_returns_404(client, db):
    _make_user(db, "chat_404")
    headers = _login(client, "chat_404", "pass1234")

    res = client.get(
        f"/api/v1/ai-chat/sessions/{uuid.uuid4()}/messages", headers=headers
    )

    assert res.status_code == 404, res.text


def test_anonymous_session_can_be_read_without_login(client, db):
    """AI 客服允许未登录使用：匿名会话仅靠 UUID 保密性保护。"""
    session = _make_session(db, owner=None)

    res = client.get(f"/api/v1/ai-chat/sessions/{session.id}/messages")

    assert res.status_code == 200, res.text


def test_logged_in_user_adopts_anonymous_session(client, db):
    """先匿名聊天再登录，历史不应丢失：登录用户访问时认领该会话。"""
    session = _make_session(db, owner=None)
    user = _make_user(db, "chat_adopter")
    headers = _login(client, "chat_adopter", "pass1234")

    res = client.get(
        f"/api/v1/ai-chat/sessions/{session.id}/messages", headers=headers
    )
    assert res.status_code == 200, res.text

    db.expire_all()
    claimer = db.query(ChatSession).filter(ChatSession.id == session.id).first()
    assert claimer.user_id == user.id

    # 认领后，另一个用户就再也读不到了
    _make_user(db, "chat_latecomer")
    other = _login(client, "chat_latecomer", "pass1234")
    denied = client.get(
        f"/api/v1/ai-chat/sessions/{session.id}/messages", headers=other
    )
    assert denied.status_code == 403, denied.text


# --- 管理端 RBAC ---


def test_admin_endpoints_reject_normal_user(client, db):
    _make_user(db, "plain_user")
    headers = _login(client, "plain_user", "pass1234")

    for method, path in [
        ("get", "/api/v1/admin/dashboard"),
        ("get", "/api/v1/admin/users"),
        ("get", "/api/v1/admin/orders"),
        ("get", "/api/v1/admin/refunds"),
        ("get", "/api/v1/admin/knowledge"),
    ]:
        res = getattr(client, method)(path, headers=headers)
        assert res.status_code == 403, f"{method.upper()} {path} -> {res.status_code}"


def test_admin_endpoints_reject_missing_token(client):
    res = client.get("/api/v1/admin/dashboard")

    assert res.status_code in (401, 403), res.text


def test_admin_endpoints_allow_admin(client, db):
    _make_user(db, "boss_admin", role=UserRole.ADMIN)
    headers = _login(client, "boss_admin", "pass1234")

    res = client.get("/api/v1/admin/dashboard", headers=headers)

    assert res.status_code == 200, res.text
    assert "total_users" in res.json()


# --- 被禁用的账号 ---


def test_disabled_user_is_treated_as_anonymous(client, db):
    """修复前 get_optional_user 不校验 is_active：禁用账号后，对方拿着旧 token
    依然能打开 AI 客服并读到历史，禁用只挡住了 /auth/me。
    """
    user = _make_user(db, "chat_disabled")
    session = _make_session(db, user)
    # 禁用前先签发一枚 token：模拟「账号被禁用，但客户端还留着登录状态」
    headers = {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}

    before = client.get(
        f"/api/v1/ai-chat/sessions/{session.id}/messages", headers=headers
    )
    assert before.status_code == 200, before.text

    user.is_active = False
    db.commit()

    after = client.get(
        f"/api/v1/ai-chat/sessions/{session.id}/messages", headers=headers
    )
    assert after.status_code == 403, after.text


def test_disabled_user_cannot_login(client, db):
    user = _make_user(db, "login_disabled")
    user.is_active = False
    db.commit()

    res = client.post(
        "/api/v1/auth/login",
        json={"username": "login_disabled", "password": "pass1234"},
    )

    assert res.status_code == 403, res.text


def test_login_does_not_reveal_whether_username_exists(client, db):
    """修复前「账号不存在」与「密码错误」是两句不同的提示，等于白送一个
    用户名枚举接口：攻击者可以先筛出已注册用户名，再针对性地撞库。
    """
    _make_user(db, "enum_target")

    existing = client.post(
        "/api/v1/auth/login",
        json={"username": "enum_target", "password": "wrong-password"},
    )
    missing = client.post(
        "/api/v1/auth/login",
        json={"username": "definitely_not_registered", "password": "wrong-password"},
    )

    assert existing.status_code == missing.status_code == 401
    assert existing.json()["detail"] == missing.json()["detail"]


# --- 订单水平越权 ---


def test_cannot_read_or_pay_another_users_order(client, db):
    """订单接口一律按 user_id 过滤，别人的订单一律 404。

    刻意不返回 403：403 等于告诉对方「这个订单号真实存在」。
    """
    owner = _make_user(db, "order_owner")
    _make_user(db, "order_intruder")
    product = create_product(db, name="越权商品", skus=[("S", {}, 10, 5)])
    address = create_address(db, owner)
    owner_headers = _login(client, "order_owner", "pass1234")
    intruder_headers = _login(client, "order_intruder", "pass1234")

    client.post(
        "/api/v1/cart/items",
        json={"product_id": product.id, "sku_id": product.skus[0].id, "quantity": 1},
        headers=owner_headers,
    )
    order = client.post(
        "/api/v1/orders", json={"address_id": address.id}, headers=owner_headers
    ).json()

    assert (
        client.get(f"/api/v1/orders/{order['id']}", headers=intruder_headers)
    ).status_code == 404
    assert (
        client.post(f"/api/v1/orders/{order['id']}/pay", headers=intruder_headers)
    ).status_code == 404
    assert (
        client.put(f"/api/v1/orders/{order['id']}/cancel", headers=intruder_headers)
    ).status_code == 404

    # 越权请求不能改变订单状态
    still = client.get(f"/api/v1/orders/{order['id']}", headers=owner_headers)
    assert still.json()["status"] == "pending_pay"
