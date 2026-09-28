import hashlib
import re
from typing import Optional, List

import jieba
from sqlalchemy import case, or_
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.core.cache import cache_delete, cache_delete_prefix, cache_get, cache_set
from app.core.config import settings
from app.models.product import Product, Category, ProductStatus
from app.models.sku import ProductSku
from app.schemas.product import CategoryOut, ProductOut

# --- 缓存键 ---
# 列表缓存按「查询参数哈希」区分，键会越攒越多，所以失效时按前缀整体清掉
_PRODUCT_DETAIL_PREFIX = "product:detail:"
# 末位的 v2 是给搜索结果用的：检索语义变了（整串匹配 → 分词匹配），
# 带上版本号可以让旧缓存自然失配，而不是等 60 秒 TTL 过期——
# 否则「改了逻辑但用户还看到旧结果」会被当成没改好。
_PRODUCT_LIST_PREFIX = "product:list:v2:"
_CATEGORY_KEY = "product:categories"

# --- 搜索 ---
# 同义词是**单向**的：只从中文泛称扩展到对应的英文品牌 / 品类词，反过来不扩展。
# 这样搜「苹果」能出 iPhone（商品名里只有 iPhone，没有「苹果」二字），
# 而搜「iPhone」只会出 iPhone——做成双向的话，搜具体型号时会混进同品牌的其他商品
# （实测：双向扩展时搜 iPhone 会带出 Apple Watch）。
# 真实系统靠搜索引擎的同义词词典或商品标签体系做这件事，这里只是最小可用版本。
_SEARCH_ALIASES = {
    "苹果": ("iphone", "apple"),
    "笔记本": ("macbook", "thinkpad", "notebook"),
    "耳机": ("airpods", "headphone"),
    "平板": ("ipad", "matepad"),
}

_CJK_ONLY = re.compile(r"^[\u4e00-\u9fff]+$")
_TERM_SPLIT = re.compile(r"[\s,，、;；/|+]+")

# 中文名词常带「子/儿」后缀（鞋子、帽子、袜子），而商品文案里往往只写核心词
# （运动鞋、鸭舌帽）。只在**严格匹配没有任何结果**时才截断后缀，理由是精度：
# 始终截断的话，搜「电子」会顺带匹配所有含「电」的商品（电池、电视……）。
# 刻意不剥「头」——「镜头」剥成「镜」会匹配到眼镜、镜子，过宽。
_CJK_NOUN_SUFFIXES = ("子", "儿")

# 「子」不是后缀、而是词本身的一部分的词——这类不能截断，否则精度掉得厉害。
# 实测：没有这个例外表时，搜「电子」因为严格匹配为空而放宽成「电」，
# 结果一次性带回充电宝、鼠标、耳机、吸尘器共 7 条。
# 真实系统的做法是用分词平台 + 同义词库维护这类规则，这里用一份小词表兜住。
_NO_SUFFIX_STRIP = frozenset(
    {
        "电子", "原子", "量子", "分子", "离子", "光子", "粒子",
        "男子", "女子", "妻子", "孩子", "王子", "太子", "君子", "弟子", "汉子", "骗子",
    }
)


def _relaxed_keyword(keyword: str) -> Optional[str]:
    """把所有以「子/儿」结尾的中文片段去掉后缀，返回放宽后的关键词。

    没有任何片段可截断时返回 None，调用方据此跳过额外的 count 查询。
    """
    parts: List[str] = []
    changed = False
    for chunk in _TERM_SPLIT.split(keyword.strip()):
        if not chunk:
            continue
        if (
            len(chunk) > 1
            and _CJK_ONLY.match(chunk)
            and chunk not in _NO_SUFFIX_STRIP
            and chunk.endswith(_CJK_NOUN_SUFFIXES)
        ):
            parts.append(chunk[:-1])
            changed = True
        else:
            parts.append(chunk)
    return " ".join(parts) if changed else None


def _search_terms(keyword: str) -> List[List[str]]:
    """把关键词切成「词 → 同义词组」，返回 ``[[词1及其同义词...], [词2...]]``。

    切分：先按空白和常见分隔符切；再把每个纯中文片段用 jieba 切一层
    （「华为手机」→ 华为 + 手机）。这一步是「模糊搜索」的关键——不做的话
    「华为手机」会被当成一个整串去匹配，而没有任何商品名里含这四个字，
    用户看到的就是「搜什么都搜不到」。

    词与词之间是 AND，词内同义词之间是 OR。
    """
    terms: List[str] = []
    for chunk in _TERM_SPLIT.split(keyword.strip()):
        if not chunk:
            continue
        tokens: List[str] = []
        if _CJK_ONLY.match(chunk) and len(chunk) > 2:
            tokens = [
                token
                for token in jieba.lcut(chunk)
                if len(token) >= 2 and _CJK_ONLY.match(token)
            ]
        # 切出多个词就用词（「华为手机」→ 华为 + 手机）；
        # 只切出一个词、或本来就是单个词时，用原串，别把它拆碎。
        # 注意不能「原串 + 分词」都放进条件里：那样会变成 AND，
        # 等于要求商品名里含「华为手机」这四个字，反而搜不到。
        terms.extend(tokens if len(tokens) > 1 else [chunk])

    groups: List[List[str]] = []
    seen = set()
    for term in terms:
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        groups.append([term, *_SEARCH_ALIASES.get(key, ())])
    return groups


def _sku_name_matches(db: Session, term: str):
    """该商品的任一 SKU 名称包含 term。

    用 EXISTS 子查询而不是 join SKU 表：join 会让一个商品按 SKU 数量出现多行，
    分页和 total 都会算错。搜 SKU 名称同时覆盖了颜色/容量这类规格——
    种子数据里规格值（「雅丹黑」「512GB」）本来就写在 SKU 名称里。
    """
    pattern = f"%{term}%"
    return (
        db.query(ProductSku.id)
        .filter(ProductSku.product_id == Product.id, ProductSku.name.ilike(pattern))
        .exists()
    )


def _apply_keyword_filter(query, db: Session, keyword: str):
    """给查询加上关键词过滤，返回 ``(query, 名称命中得分表达式)``。

    列表搜索与 AI 客服的商品兜底共用这一份实现——同一件事写两遍迟早会漂移。
    """
    term_groups = _search_terms(keyword)
    if not term_groups:
        return query, None

    query = query.outerjoin(Category, Product.category_id == Category.id)
    for synonyms in term_groups:
        # 同一个词的同义词之间取 OR，不同词之间取 AND
        query = query.filter(
            or_(
                *[
                    or_(
                        Product.name.ilike(f"%{term}%"),
                        Product.description.ilike(f"%{term}%"),
                        Category.name.ilike(f"%{term}%"),
                        _sku_name_matches(db, term),
                    )
                    for term in synonyms
                ]
            )
        )

    # 名称命中的排前面：搜「手机」时，名字里就带手机的商品应该比只在描述里
    # 提了一句的靠前。用 SUM(CASE ...) 数命中词数当相关度。
    name_hit_score = sum(
        case((Product.name.ilike(f"%{term}%"), 1), else_=0)
        for synonyms in term_groups
        for term in synonyms
    )
    return query, name_hit_score


def _on_sale_products(db: Session):
    """在售商品的查询底座（关掉重排/过滤之前的原始查询）。"""
    return (
        db.query(Product)
        .options(selectinload(Product.skus), selectinload(Product.category))
        .filter(Product.status == ProductStatus.ON)
    )


def invalidate_product_cache(product_id: Optional[int] = None) -> None:
    """商品或分类变动后清缓存。

    详情按 id 精确删；列表与分类直接按前缀整体清——列表的组合（分页 × 关键词 ×
    排序）太多，逐个追踪既费劲又容易漏，而这个规模的缓存重建成本极低。
    """
    if product_id is not None:
        cache_delete(f"{_PRODUCT_DETAIL_PREFIX}{product_id}")
    cache_delete_prefix(_PRODUCT_LIST_PREFIX)
    cache_delete(_CATEGORY_KEY)


def _to_json(model) -> dict:
    """Pydantic 模型 → JSON 安全的 dict。

    统一走 ``mode="json"``：Decimal 会变成字符串，与响应序列化的结果一致，
    因此「缓存命中」与「缓存未命中」返回的结构完全相同，不会出现类型漂移。
    """
    return model.model_dump(mode="json")


def _apply_skus(
    product: Product, skus_data: Optional[List[dict]], allow_remove: bool = True
) -> None:
    """重建商品的 SKU，并同步商品级价格/库存聚合值。"""
    if skus_data is None:
        return

    existing_by_id = {sku.id: sku for sku in product.skus}
    kept_ids = set()

    for sku_item in skus_data:
        sku_id = sku_item.get("id")
        if sku_id and sku_id in existing_by_id:
            sku = existing_by_id[sku_id]
            sku.name = sku_item["name"]
            sku.specs = sku_item.get("specs") or {}
            sku.price = sku_item["price"]
            sku.stock = sku_item.get("stock") or 0
            kept_ids.add(sku_id)
        else:
            product.skus.append(
                ProductSku(
                    name=sku_item["name"],
                    specs=sku_item.get("specs") or {},
                    price=sku_item["price"],
                    stock=sku_item.get("stock") or 0,
                )
            )

    if allow_remove:
        for old in list(product.skus):
            if old.id not in kept_ids:
                product.skus.remove(old)

    _sync_product_aggregates(product)


def _sync_product_aggregates(product: Product) -> None:
    """用 SKU 汇总商品默认展示价与总库存。"""
    if product.skus:
        product.price = min(sku.price for sku in product.skus)
        product.stock = sum(sku.stock for sku in product.skus)


def _ensure_default_sku(product: Product) -> None:
    if not product.skus:
        product.skus.append(
            ProductSku(
                name="默认规格",
                specs={},
                price=product.price,
                stock=product.stock,
            )
        )


def get_products(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    category_id: Optional[int] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    """公开商品列表（仅上架），支持搜索、分类筛选、排序、分页。

    结果按查询参数缓存 ``CACHE_PRODUCT_TTL`` 秒。库存/销量在这里可能短暂陈旧，
    这是有意的取舍：下单路径用条件 UPDATE 在事务里再校验一次库存，
    真正保证不超卖；展示层为了抗热点读，接受秒级的陈旧。
    """
    cache_key = _PRODUCT_LIST_PREFIX + hashlib.sha1(
        f"{page}|{page_size}|{keyword}|{category_id}|{sort_by}|{sort_order}".encode()
    ).hexdigest()[:16]
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    query = _on_sale_products(db)

    name_hit_score = None
    if keyword:
        query, name_hit_score = _apply_keyword_filter(query, db, keyword)
        # 严格匹配一条都没有时，才用「去掉名词后缀」的关键词再试一次：
        # 用户搜「鞋子」，文案里写的是「运动鞋」，差的就是那个「子」。
        # 只在关键词真的以「子/儿」结尾时才多花一次 count——绝大多数搜索不受影响。
        relaxed = _relaxed_keyword(keyword)
        if relaxed and query.count() == 0:
            relaxed_query, relaxed_score = _apply_keyword_filter(
                _on_sale_products(db), db, relaxed
            )
            if relaxed_query.count():
                query, name_hit_score = relaxed_query, relaxed_score

    if category_id:
        sub_ids = [category_id]
        sub_categories = (
            db.query(Category).filter(Category.parent_id == category_id).all()
        )
        sub_ids.extend([c.id for c in sub_categories])
        query = query.filter(Product.category_id.in_(sub_ids))

    valid_sort_columns = ["created_at", "price", "sales", "stock"]
    if sort_by not in valid_sort_columns:
        sort_by = "created_at"
    sort_column = getattr(Product, sort_by, Product.created_at)

    order_by = []
    # 只有在「搜索 + 用户没显式指定排序」时才按相关度优先：
    # 用户明确点了按价格排序时，就该尊重他的选择。
    if name_hit_score is not None and sort_by == "created_at":
        order_by.append(name_hit_score.desc())
    order_by.append(sort_column.asc() if sort_order == "asc" else sort_column.desc())
    query = query.order_by(*order_by)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    for item in items:
        if item.category:
            item.category_name = item.category.name

    payload = {
        "items": [_to_json(ProductOut.model_validate(item)) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
    cache_set(cache_key, payload, settings.cache_product_ttl)
    return payload


def get_product(db: Session, product_id: int) -> Optional[dict]:
    """商品详情（仅上架），带缓存。"""
    cache_key = f"{_PRODUCT_DETAIL_PREFIX}{product_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    product = (
        db.query(Product)
        .options(selectinload(Product.skus))
        .filter(Product.id == product_id, Product.status == ProductStatus.ON)
        .first()
    )
    if product is None:
        return None
    payload = _to_json(ProductOut.model_validate(product))
    cache_set(cache_key, payload, settings.cache_product_ttl)
    return payload


def get_categories(db: Session):
    """分类树（两级），带缓存。"""
    cached = cache_get(_CATEGORY_KEY)
    if cached is not None:
        return cached

    categories = db.query(Category).order_by(Category.sort).all()
    root = [c for c in categories if c.parent_id is None]
    for r in root:
        r.children = [c for c in categories if c.parent_id == r.id]
    payload = [_to_json(CategoryOut.model_validate(c)) for c in root]
    cache_set(_CATEGORY_KEY, payload, settings.cache_product_ttl)
    return payload


def search_products(db: Session, keyword: str, limit: int = 5):
    """供 AI 客服使用的轻量商品检索（仅上架）。

    与列表搜索共用同一套分词逻辑：用户对 AI 说的是自然语言，
    整串匹配几乎必然落空，分词之后至少能命中其中的商品词。
    """
    query = (
        db.query(Product)
        .options(selectinload(Product.skus), selectinload(Product.category))
        .filter(Product.status == ProductStatus.ON)
    )
    query, name_hit_score = _apply_keyword_filter(query, db, keyword)
    order_by = []
    if name_hit_score is not None:
        order_by.append(name_hit_score.desc())
    order_by.append(Product.sales.desc())
    return query.order_by(*order_by).limit(limit).all()


# --- Admin methods ---


def admin_get_products(db: Session, page: int = 1, page_size: int = 20):
    """管理端商品列表（含下架）。"""
    query = (
        db.query(Product)
        .options(selectinload(Product.skus))
        .order_by(Product.created_at.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def admin_create_product(db: Session, data: dict) -> Product:
    product = Product(
        name=data["name"],
        description=data.get("description"),
        price=data["price"],
        stock=data.get("stock") or 0,
        images=data.get("images") or [],
        category_id=data.get("category_id"),
        status=ProductStatus(data.get("status", "on")),
    )
    db.add(product)
    db.flush()
    _apply_skus(product, data.get("skus"))
    _ensure_default_sku(product)
    _sync_product_aggregates(product)
    db.commit()
    db.refresh(product)
    invalidate_product_cache()
    return product


def admin_update_product(db: Session, product_id: int, data: dict) -> Optional[Product]:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return None

    skus_data = data.pop("skus", None)
    for key, value in data.items():
        if value is not None:
            if key == "status":
                value = ProductStatus(value)
            setattr(product, key, value)

    if skus_data is not None:
        from app.models.cart import CartItem
        from app.models.order import OrderItem

        referenced = (
            db.query(OrderItem.id).filter(OrderItem.product_id == product.id).first()
        ) or (
            db.query(CartItem.id).filter(CartItem.product_id == product.id).first()
        )
        if referenced:
            payload_ids = {s.get("id") for s in skus_data}
            existing_ids = {s.id for s in product.skus}
            adding_new = any(not s.get("id") for s in skus_data)
            removing_old = bool(existing_ids - payload_ids)
            if adding_new or removing_old:
                raise HTTPException(
                    status_code=400,
                    detail="商品已有购物车/订单记录，只能编辑现有 SKU 的价格与库存，不能新增/删除 SKU",
                )
        _apply_skus(product, skus_data, allow_remove=not referenced)
    db.commit()
    db.refresh(product)
    invalidate_product_cache(product.id)
    return product


def admin_delete_product(db: Session, product_id: int) -> bool:
    """删除商品。

    已有订单的商品不能物理删除：``order_items`` 还引用着 ``products.id`` 与
    ``product_skus.id``，删除会破坏历史订单（MySQL 下直接外键报错 500，
    测试用的 SQLite 又默认不校验外键，于是变成静默产生孤儿数据）。
    这种情况应改为下架。
    """
    from app.models.cart import CartItem
    from app.models.content import Favorite
    from app.models.order import OrderItem

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return False

    ordered = (
        db.query(OrderItem.id).filter(OrderItem.product_id == product_id).first()
    )
    if ordered:
        raise HTTPException(
            status_code=400,
            detail="该商品已有订单记录，不能删除；如需停售请将其下架",
        )

    # 尚未成交的引用可以直接清理，否则同样会触发外键约束
    db.query(CartItem).filter(CartItem.product_id == product_id).delete()
    db.query(Favorite).filter(Favorite.product_id == product_id).delete()
    db.delete(product)
    db.commit()
    invalidate_product_cache(product_id)
    return True


def admin_get_all_categories(db: Session):
    return db.query(Category).order_by(Category.sort).all()


def admin_create_category(db: Session, data: dict) -> Category:
    category = Category(**data)
    db.add(category)
    db.commit()
    db.refresh(category)
    invalidate_product_cache()
    return category


def admin_update_category(db: Session, category_id: int, data: dict) -> Optional[Category]:
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        return None
    for key, value in data.items():
        if value is not None:
            setattr(category, key, value)
    db.commit()
    db.refresh(category)
    invalidate_product_cache()
    return category


def admin_delete_category(db: Session, category_id: int) -> bool:
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        return False
    db.delete(category)
    db.commit()
    invalidate_product_cache()
    return True
