"""种子数据：初始化管理员、演示用户、分类、商品(SKU)、Banner、知识库与评测用例。

运行方式: cd backend && python -m app.core.seed

**商品与分类的数据不在这里**，在 ``app/core/catalog.py``：这边只负责「怎么把它
写进库」。早期两件事混在一个文件里，商品表一长（现在是 59 个商品 / 130 个 SKU）
就没人愿意改了。

整个 seed 是幂等的：已经存在的记录不会重复插入。唯一的例外是**修正历史数据的
商品图错位**，见 ``_seed_products`` 里的说明。
"""

import os

from app.ai.eval_dataset import EVAL_CASES, KNOWLEDGE_DOCS
from app.core.catalog import BANNERS, CATALOG, CATEGORY_TREE
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.chat import EvalTestCase
from app.models.content import Banner
from app.models.knowledge import KnowledgeDoc
from app.models.product import Category, Product, ProductStatus
from app.models.sku import ProductSku
from app.models.user import User, UserRole


def _img(slug: str) -> str:
    """商品图路径。文件名就是 catalog 里的 slug，统一 600x450 白底 JPEG。"""
    return f"/static/products/{slug}.jpg"


def _cat_id(db, name):
    category = db.query(Category).filter(Category.name == name).first()
    return category.id if category else None


def _seed_users(db):
    if not db.query(User).filter(User.username == "admin").first():
        db.add(
            User(
                username="admin",
                password_hash=hash_password("admin123"),
                email="admin@mall.com",
                role=UserRole.ADMIN,
            )
        )
        db.commit()
        print("[OK] admin / admin123")

    if not db.query(User).filter(User.username == "demo").first():
        db.add(
            User(
                username="demo",
                password_hash=hash_password("demo123"),
                email="demo@mall.com",
                phone="13800138000",
            )
        )
        db.commit()
        print("[OK] demo / demo123")


def _seed_categories(db):
    """按名称幂等补齐分类树，可以在已有库上增量执行。"""
    added = 0
    for root_name, root_sort, subs in CATEGORY_TREE:
        root = (
            db.query(Category)
            .filter(Category.name == root_name, Category.parent_id.is_(None))
            .first()
        )
        if not root:
            root = Category(name=root_name, sort=root_sort)
            db.add(root)
            db.flush()
            added += 1

        existing_subs = {
            c.name for c in db.query(Category).filter(Category.parent_id == root.id)
        }
        for idx, sub_name in enumerate(subs, start=1):
            if sub_name not in existing_subs:
                db.add(Category(name=sub_name, parent_id=root.id, sort=idx))
                added += 1

    if added:
        db.commit()
        print(f"[OK] categories added: {added}")


def _seed_products(db):
    existing_names = {p.name for p in db.query(Product).all()}
    added = 0
    for name, desc, price, cat_name, slug, sales, skus in CATALOG:
        if name in existing_names:
            continue
        product = Product(
            name=name,
            description=desc,
            price=price,
            # 商品级库存 = 各 SKU 库存之和；下单走的是 SKU 库存，
            # 这个字段只是列表页展示用（见 Product 模型里的说明）。
            stock=sum(sku[3] for sku in skus),
            images=[_img(slug)],
            category_id=_cat_id(db, cat_name),
            status=ProductStatus.ON,
            sales=sales,
        )
        db.add(product)
        db.flush()
        for sku_name, specs, sku_price, sku_stock in skus:
            db.add(
                ProductSku(
                    product_id=product.id,
                    name=sku_name,
                    specs=specs,
                    price=sku_price,
                    stock=sku_stock,
                )
            )
        existing_names.add(name)
        added += 1
    if added:
        db.commit()
        print(f"[OK] products with SKUs added: {added}")

    # 修正历史数据的商品图错位。
    #
    # 上一版种子数据的图片映射是错的：`IMG` 的键名和图片内容完全对不上
    # （`phone_1` 是 AirPods、`watch` 是冰箱广告、`tea` 是手机照片），
    # 17 个商品里只有 Nike 那一个图是对的。已经写进库的旧记录不会因为改了
    # 种子文件就自己变好，所以这里补一次。
    #
    # 刻意只同步 images 一个字段：其它字段仍然保持「已存在就不动」，
    # 免得把人在后台改过的价格/描述覆盖掉。
    expected = {item[0]: [_img(item[4])] for item in CATALOG}
    fixed = 0
    for product in db.query(Product).all():
        want = expected.get(product.name)
        if want and list(product.images or []) != want:
            product.images = want
            fixed += 1
    if fixed:
        db.commit()
        print(f"[OK] 修正了 {fixed} 个历史商品的图片错位")


def _backfill_skus(db):
    """兼容极早期数据：没有 SKU 的商品补一个默认规格，否则下单会直接报错。"""
    backfilled = 0
    for product in db.query(Product).all():
        if not product.skus:
            db.add(
                ProductSku(
                    product_id=product.id,
                    name="默认规格",
                    specs={},
                    price=product.price,
                    stock=product.stock,
                )
            )
            backfilled += 1
    if backfilled:
        db.commit()
        print(f"[OK] backfilled {backfilled} default SKU(s)")


def _seed_banners(db):
    if db.query(Banner).count():
        return
    for title, slug, link, sort in BANNERS:
        db.add(Banner(title=title, image=_img(slug), link=link, sort=sort))
    db.commit()
    print(f"[OK] banners: {len(BANNERS)}")


def _seed_knowledge(db):
    existing_titles = {d.title for d in db.query(KnowledgeDoc.title).all()}
    added = 0
    for title, category, content in KNOWLEDGE_DOCS:
        if title in existing_titles:
            continue
        db.add(KnowledgeDoc(title=title, content=content, category=category))
        existing_titles.add(title)
        added += 1
    if added:
        db.commit()
        print(f"[OK] knowledge docs added: {added}")


def _seed_eval_cases(db):
    if db.query(EvalTestCase).count():
        return
    for question, title in EVAL_CASES:
        db.add(EvalTestCase(question=question, expected_title=title))
    db.commit()
    print(f"[OK] eval cases: {len(EVAL_CASES)}")


def seed(db):
    _seed_users(db)
    _seed_categories(db)
    _seed_products(db)
    _backfill_skus(db)
    _seed_banners(db)
    _seed_knowledge(db)
    _seed_eval_cases(db)


def sync_vector_index(db):
    """把知识库同步进向量索引；不需要时（或失败时）都不阻断 seed。"""
    if os.environ.get("SEED_SKIP_VECTOR", "").lower() in ("1", "true", "yes"):
        # CI 里跑端到端测试时用：同步向量索引会去下载 100MB 的 BGE 模型，
        # 而那套用例根本不碰知识库。
        print("[SKIP] SEED_SKIP_VECTOR=1，跳过向量索引同步")
        return
    if not db.query(KnowledgeDoc).count():
        return
    try:
        from app.ai.indexer import sync_all_knowledge

        count = sync_all_knowledge(db)
        print(f"[OK] vector index synced ({count} chunks)")
    except Exception as exc:
        print(f"[WARN] vector index sync skipped: {exc}")


def main():
    db = SessionLocal()
    try:
        seed(db)
        sync_vector_index(db)
        print("[DONE] seed finished")
    finally:
        db.close()


if __name__ == "__main__":
    main()
