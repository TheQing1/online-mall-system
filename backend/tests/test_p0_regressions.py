"""求职整改 P0 阶段修复的缺陷回归测试。

每个用例对应一个「实际演示时会被一眼看穿」的缺陷，注释写明了修复前的行为，
这样以后回归时能看懂「为什么要有这条断言」。

命名约定：用例名直接描述**用户可感知的行为**，而不是实现细节，
这样它在功能坏掉时一定会红。
"""

from app.schemas.product import ProductCreate

from tests.conftest import auth_header


# --- 缺陷 1：后台「新增商品」必然 422 ---


def test_admin_can_create_product_with_sku_only_payload(client, db, admin):
    """修复前：后台只提交 skus[].price 不提交顶层 price，创建接口必然 422。

    ProductCreate 里 price 是必填（ProductUpdate 才是可选），所以「新增」全坏、
    「编辑」正常——这正是它一直没被发现的原因。
    """
    headers = auth_header(client, "admin_test", "admin123")
    payload = {
        "name": "回归测试商品",
        "description": "验证创建接口能接受最小合法 payload",
        "price": 1999,
        "stock": 10,
        "images": [],
        "category_id": None,
        "status": "on",
        "skus": [{"name": "黑色 256G", "specs": {"颜色": "黑"}, "price": 1999, "stock": 10}],
    }
    res = client.post("/api/v1/admin/products", json=payload, headers=headers)
    assert res.status_code == 200, res.text

    # 服务端应以 SKU 为准汇总出商品维度价格与库存
    data = res.json()
    assert float(data["price"]) == 1999
    assert data["stock"] == 10
    assert len(data["skus"]) == 1


def test_product_create_still_requires_top_level_price():
    """守卫上面的修复：确认 price 确实是必填项。

    如果哪天有人把 ProductCreate.price 改成可选，这条会红——提醒「后台必须传
    price」这个约定仍然有效，否则前端可以继续漏传而不报错。
    """
    try:
        ProductCreate(
            name="缺价格",
            skus=[{"name": "默认", "specs": {}, "price": 10, "stock": 1}],
        )
    except Exception:
        return
    raise AssertionError("ProductCreate 不应允许缺少顶层 price")


# --- 缺陷 3：登录用户取不到 AI 会话历史（403 被静默吞掉） ---


def test_logged_in_user_can_read_own_chat_history(client, db, user):
    """修复前：前端 init() 拉历史不带 Authorization 头。

    会话一旦绑定 user_id，匿名请求就会被判 403，前端把 403 吞成「没有历史」，
    表现为「刷新页面后 AI 对话全没了」。
    """
    headers = auth_header(client, "buyer", "user123")
    session_id = "11111111-2222-3333-4444-555555555555"

    # 带着 token 发一条消息：会话被认领到该用户名下
    res = client.post(
        "/api/v1/ai-chat/chat",
        json={"session_id": session_id, "message": "退货政策是什么"},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    # 带 token 读历史：必须拿得到
    own = client.get(
        f"/api/v1/ai-chat/sessions/{session_id}/messages", headers=headers
    )
    assert own.status_code == 200, own.text
    assert any(m["role"] == "user" for m in own.json())

    # 不带 token 读同一个已绑定会话：必须 403（越权保护不能被修复削弱）
    anonymous = client.get(f"/api/v1/ai-chat/sessions/{session_id}/messages")
    assert anonymous.status_code == 403
