import hashlib
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.core.cache import (
    cache_delete,
    cache_delete_prefix,
    cache_get_or_load,
    jittered_ttl,
)
from app.core.config import settings
from app.models.product import Product, Category, ProductStatus
from app.models.sku import ProductSku
from app.schemas.product import CategoryOut, ProductOut
from app.services import search

# --- 缓存键 ---
# 列表缓存按「查询参数哈希」区分，键会越攒越多，所以失效时按前缀整体清掉
_PRODUCT_DETAIL_PREFIX = "product:detail:"
# 末位的 v2 是给搜索结果用的：检索语义变了（整串匹配 → 分词匹配），
# 带上版本号可以让旧缓存自然失配，而不是等 60 秒 TTL 过期——
# 否则「改了逻辑但用户还看到旧结果」会被当成没改好。
_PRODUCT_LIST_PREFIX = "product:list:v2:"
_CATEGORY_KEY = "product:categories"


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

    结果按查询参数缓存 ``CACHE_PRODUCT_TTL`` 秒（带抖动）。库存/销量在这里可能
    短暂陈旧，这是有意的取舍：下单路径用条件 UPDATE 在事务里再校验一次库存，
    真正保证不超卖；展示层为了抗热点读，接受秒级的陈旧。
    """
    cache_key = _PRODUCT_LIST_PREFIX + hashlib.sha1(
        f"{page}|{page_size}|{keyword}|{category_id}|{sort_by}|{sort_order}".encode()
    ).hexdigest()[:16]
    return cache_get_or_load(
        cache_key,
        jittered_ttl(settings.cache_product_ttl),
        lambda: _load_products(
            db, page, page_size, keyword, category_id, sort_by, sort_order
        ),
    )


def _load_products(
    db: Session,
    page: int,
    page_size: int,
    keyword: Optional[str],
    category_id: Optional[int],
    sort_by: str,
    sort_order: str,
) -> dict:
    """真正查库并组装列表响应（缓存的加载器）。"""
    # 查询理解（归一化 / 分词 / 同义词 / AND→OR 兜底）全在 search 层，
    # 这里只管分页、排序与缓存
    query, name_hit_score = search.apply_product_search(
        db, _on_sale_products(db), keyword
    )

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
    return payload


def get_product(db: Session, product_id: int) -> Optional[dict]:
    """商品详情（仅上架），带缓存与负缓存。

    不存在的 id 也会缓存一小会儿：否则有人拿随机 id 刷接口时，每次都会绕开
    缓存直接查库——这就是**缓存穿透**。
    """
    cache_key = f"{_PRODUCT_DETAIL_PREFIX}{product_id}"
    return cache_get_or_load(
        cache_key,
        jittered_ttl(settings.cache_product_ttl),
        lambda: _load_product(db, product_id),
        negative_ttl=settings.cache_negative_ttl,
    )


def _load_product(db: Session, product_id: int) -> Optional[dict]:
    product = (
        db.query(Product)
        # 分类也要 eager load：详情页要显示「分类: xxx」，以前这里没设
        # category_name（列表接口设了、详情接口漏了），于是每个商品详情页
        # 都显示「分类: 未分类」。同一个字段两条路径行为不一致，是很容易漏的 bug。
        .options(selectinload(Product.skus), selectinload(Product.category))
        .filter(Product.id == product_id, Product.status == ProductStatus.ON)
        .first()
    )
    if product is None:
        return None
    if product.category:
        product.category_name = product.category.name
    return _to_json(ProductOut.model_validate(product))


def get_categories(db: Session):
    """分类树（两级），带缓存。"""
    return cache_get_or_load(
        _CATEGORY_KEY,
        jittered_ttl(settings.cache_product_ttl),
        lambda: _load_categories(db),
    )


def _load_categories(db: Session) -> list:
    categories = db.query(Category).order_by(Category.sort).all()
    root = [c for c in categories if c.parent_id is None]
    for r in root:
        r.children = [c for c in categories if c.parent_id == r.id]
    return [_to_json(CategoryOut.model_validate(c)) for c in root]


def search_products(db: Session, keyword: str, limit: int = 5):
    """供 AI 客服使用的轻量商品检索（仅上架）。

    与列表搜索共用同一套分词逻辑：用户对 AI 说的是自然语言，
    整串匹配几乎必然落空，分词之后至少能命中其中的商品词。
    """
    query, name_hit_score = search.apply_product_search(
        db, _on_sale_products(db), keyword
    )
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
