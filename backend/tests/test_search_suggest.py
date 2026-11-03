"""搜索建议（自动补全）的测试。

两条最关键的性质：

1. **补全 ≠ 检索**。检索要「找全」（同义词扩展、AND→OR 兜底），
   补全要「补全」（只要字面前缀/子串命中）。把两者混在一起会让下拉里
   出现一堆「因为近义才相关」的候选，用户顺着它去搜反而搜到空结果页。
2. **同义词是"反向"用的**。用户敲「鞋子」时该带出「运动鞋」
   （同义词表把鞋子映射到鞋，候选「运动鞋」包含「鞋」），这是补全该做的事。
"""

import pytest

from app.models.product import Category, ProductStatus
from app.services.search import suggest

from tests.conftest import create_product


def _texts(items):
    return [item["text"] for item in items]


@pytest.fixture()
def make_product(db):
    """造商品的小工厂：默认上架，可指定下架。"""
    created = []

    def _make(name: str, status_off: bool = False):
        product = create_product(db, name=name)
        if status_off:
            product.status = ProductStatus.OFF
            db.commit()
        created.append(product)
        return product

    return _make


# --- 字面补全 ---


def test_prefix_match_ranks_before_substring(db, make_product):
    """前缀命中必须排在中段命中之前。

    用户敲「手机」时，「手机数码旗舰店款」比「测试手机专用支架」
    更可能是他想要的东西。
    """
    make_product("测试手机专用支架")
    make_product("手机数码旗舰店款")

    texts = _texts(suggest("手机", db=db))
    assert texts, "应该有候选"

    prefix_indexes = [i for i, t in enumerate(texts) if t.startswith("手机")]
    other_indexes = [i for i, t in enumerate(texts) if not t.startswith("手机")]
    if prefix_indexes and other_indexes:
        assert max(prefix_indexes) < min(other_indexes), f"前缀命中没排前面：{texts}"


def test_empty_query_returns_nothing(db):
    """空输入不该返回候选——否则输入框一聚焦就弹一大堆。"""
    assert suggest("", db=db) == []
    assert suggest("   ", db=db) == []


def test_no_match_returns_empty(db):
    """完全不存在的关键词返回空列表（前端据此显示「没有找到」）。"""
    assert suggest("zzz绝对不存在的商品zzz", db=db) == []


def test_respects_limit(db, make_product):
    for i in range(20):
        make_product(f"限流测试手机{i}")

    assert len(suggest("限流测试", limit=5, db=db)) <= 5


# --- 同义词反向补全（最易写错的地方）---


def test_synonym_expands_to_related_products(db, make_product):
    """敲「鞋子」应该补全到「运动鞋」类商品。

    同义词表：鞋子 -> 鞋；候选「运动鞋」包含「鞋」→ 命中。

    这里曾有个 bug：为了「过滤噪音」加了 `len(term) >= 2`，
    把中文单字同义词（鞋/帽/袜/裤/裙）全过滤掉了，整条链断掉。
    噪音该靠**排序**处理，不该在匹配阶段排除——排除掉就再也回不来。
    """
    make_product("专业运动鞋")

    texts = _texts(suggest("鞋子", db=db))
    assert any("运动鞋" in t for t in texts), f"同义词补全失效：{texts}"


def test_synonym_english_brand(db, make_product):
    """敲「苹果」应该带出 iPhone / Apple 系列。"""
    make_product("iPhone 15 Pro Max")
    make_product("Apple Watch Series 9")

    texts = _texts(suggest("苹果", db=db))
    assert any("iPhone" in t or "Apple" in t for t in texts), (
        f"英文品牌同义词补全失效：{texts}"
    )


# --- 结果结构与过滤 ---


def test_items_have_type_field(db, make_product):
    """每条候选必须带 type，前端据此显示「分类 / 规格」标签。"""
    make_product("结构测试手机")

    for item in suggest("结构测试", db=db):
        assert item.get("type") in {"product", "category", "sku"}
        assert item.get("text")


def test_stopped_products_are_excluded(db, make_product):
    """下架商品不该出现在候选里——补出来点进去是 404。"""
    make_product("已下架测试商品", status_off=True)

    texts = _texts(suggest("已下架测试", db=db))
    assert not any("已下架测试商品" in t for t in texts), (
        f"下架商品出现在候选中：{texts}"
    )


def test_category_names_are_suggested(db):
    """分类名也是候选来源（用户可能直接搜品类，而不是具体商品）。"""
    db.add(Category(name="测试数码分类"))
    db.commit()

    items = suggest("测试数码", db=db)
    assert any(item["type"] == "category" for item in items), (
        f"分类没被纳入候选：{_texts(items)}"
    )
