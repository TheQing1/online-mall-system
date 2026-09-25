"""鉴权与越权（IDOR）回归测试。

这些用例对应项目审计中发现的问题：
- ``api/users.py`` 用到了 ``status`` 却没 import，访问不存在的地址会 500；
- ``api/ai_chat.py`` 的会话接口没有归属校验，任何拿到 session_id 的人都能读/删；
- 管理端接口缺少「普通用户访问应被拒绝」的断言。
"""

import uuid

from app.models.chat import ChatMessage, ChatSession
from app.models.user import User, UserRole
from app.core.security import hash_password


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
    user = _make_user(db, "addr_user")
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
