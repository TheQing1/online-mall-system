"""商品搜索：分词、多词组合、同义词与 SKU 匹配。

背景（真实反馈）：原来的搜索是把整个关键词当一个子串去 LIKE，
于是「苹果」搜不到那台叫 iPhone 的商品、「华为手机」这种组合必然搜不到、
按颜色/容量（「雅丹黑」）也搜不到——用户看到的现象就是「搜索不好用」。
"""

from app.models.product import Category, Product, ProductStatus
from app.models.sku import ProductSku


def _make_category(db, name):
    category = Category(name=name, parent_id=None, sort=0)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def _make_product(db, name, description, category=None, skus=None, sales=0):
    product = Product(
        name=name,
        description=description,
        price=min(s[1] for s in skus) if skus else 100,
        stock=sum(s[2] for s in skus) if skus else 1,
        images=[],
        category_id=category.id if category else None,
        status=ProductStatus.ON,
        sales=sales,
    )
    db.add(product)
    db.flush()
    for sku_name, price, stock, specs in skus or [("默认规格", 100, 1, {})]:
        db.add(
            ProductSku(
                product_id=product.id,
                name=sku_name,
                specs=specs,
                price=price,
                stock=stock,
            )
        )
    db.commit()
    db.refresh(product)
    return product


def _search(client, keyword, **params):
    res = client.get("/api/v1/products", params={"keyword": keyword, **params})
    assert res.status_code == 200, res.text
    payload = res.json()
    return [item["name"] for item in payload["items"]], payload["total"]


def _seed_catalog(db):
    phone = _make_category(db, "手机")
    laptop = _make_category(db, "笔记本")
    _make_product(
        db,
        "华为 Mate 60 Pro",
        "麒麟 9000S 芯片，卫星通话，IP68 防水防尘。",
        phone,
        skus=[("雅丹黑 12+512GB", 6999, 5, {"颜色": "雅丹黑"})],
        sales=218,
    )
    _make_product(
        db,
        "iPhone 15 Pro Max",
        "A17 Pro 芯片，钛金属边框，4800 万像素三摄。",
        phone,
        skus=[("原色钛金属 256GB", 9999, 5, {"颜色": "原色钛金属"})],
        sales=326,
    )
    _make_product(
        db,
        "MacBook Pro 14 英寸",
        "M3 Pro 芯片，18GB 统一内存，适合高性能办公与创作。",
        laptop,
        skus=[("深空黑 18+1TB", 14999, 3, {"颜色": "深空黑"})],
        sales=88,
    )
    _make_product(
        db,
        "Apple Watch Series 9",
        "支持全天候视网膜显示屏与双指互点手势。",
        None,
        skus=[("午夜色 45mm", 3199, 4, {})],
        sales=60,
    )


def test_multi_word_query_matches_all_terms(client, db):
    """「华为手机」应命中华为的手机，而不是把整串当一个子串去匹配。"""
    _seed_catalog(db)

    names, total = _search(client, "华为手机")

    assert names == ["华为 Mate 60 Pro"]
    assert total == 1


def test_word_order_does_not_matter(client, db):
    _seed_catalog(db)

    assert _search(client, "华为手机")[0] == _search(client, "手机 华为")[0]


def test_all_terms_must_match(client, db):
    """多词之间是 AND：只满足一个词的商品不该被搜出来。"""
    _seed_catalog(db)

    names, _total = _search(client, "华为 笔记本")

    assert names == []


def test_chinese_alias_matches_english_product_name(client, db):
    """搜「苹果」要能找到商品名里只有 iPhone / Apple 的商品。"""
    _seed_catalog(db)

    names, _total = _search(client, "苹果")

    assert set(names) == {"iPhone 15 Pro Max", "Apple Watch Series 9"}


def test_alias_expansion_is_one_way(client, db):
    """单向扩展：搜具体型号不该混进同品牌的其他商品。"""
    _seed_catalog(db)

    # 「苹果」会扩展出 iphone/apple（两个都出）；
    # 但搜「iPhone」不扩展回 apple，所以不会带出 Apple Watch。
    assert _search(client, "iPhone")[0] == ["iPhone 15 Pro Max"]
    assert _search(client, "apple")[0] == ["Apple Watch Series 9"]


def test_search_matches_sku_name_and_spec(client, db):
    """颜色/容量这类规格写在 SKU 名称里，也该能被搜到。"""
    _seed_catalog(db)

    assert _search(client, "雅丹黑")[0] == ["华为 Mate 60 Pro"]
    assert _search(client, "深空黑")[0] == ["MacBook Pro 14 英寸"]
    assert _search(client, "512GB")[0] == ["华为 Mate 60 Pro"]
    assert _search(client, "1TB")[0] == ["MacBook Pro 14 英寸"]


def test_case_insensitive_for_english(client, db):
    _seed_catalog(db)

    assert _search(client, "macbook")[0] == ["MacBook Pro 14 英寸"]
    assert _search(client, "MACBOOK")[0] == ["MacBook Pro 14 英寸"]


def test_name_match_ranks_before_description_match(client, db):
    """名称命中优先于只在描述里提过一句的商品。"""
    db.add(
        _make_category(db, "数码")  # 保证分类表非空，避免影响其它断言
    )
    _make_product(db, "无线降噪耳机", "通勤路上接手机电话用的降噪耳机。", None, sales=10)
    _make_product(db, "手机支架", "夹在桌边，方便看手机的配件。", None, sales=99)

    # 「手机」在第二个商品的名字里、第一个商品的描述里
    names, _total = _search(client, "手机")

    assert names.index("手机支架") < names.index("无线降噪耳机")


def test_no_match_returns_empty(client, db):
    """不能退化成「搜什么都返回全部」。"""
    _seed_catalog(db)

    names, total = _search(client, "完全不存在的商品词")

    assert names == []
    assert total == 0


def test_explicit_sort_is_respected(client, db):
    """用户显式按价格排序时，相关度不该盖过他的选择。"""
    _seed_catalog(db)

    names, _total = _search(client, "手机", sort_by="price", sort_order="asc")

    assert names == ["华为 Mate 60 Pro", "iPhone 15 Pro Max"]
