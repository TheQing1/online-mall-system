"""真实 MySQL / InnoDB 下的集成测试。

为什么单独一份：`test_stock.py` 的并发用例跑在 SQLite 上，而 SQLite 只是
把写操作整体串行化，**验证不了 InnoDB 的行锁与 `UPDATE ... WHERE stock >= ?`
的条件更新语义**——也就是生产环境真正的防超卖机制。这里补上这一环。

默认连接 ``<MYSQL_DATABASE>_test``（可通过 ``TEST_MYSQL_DATABASE`` /
``TEST_MYSQL_URL`` 覆盖）。连不上 MySQL 时整个模块 skip，CI 不会因此变红。
若库名以 ``_test`` 结尾，测试结束会直接删库，不在你的 MySQL 上留垃圾。
"""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy import inspect as sa_inspect

from app.core.config import settings
from app.core.security import hash_password
from app.models.base import Base
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.sku import ProductSku
from app.models.user import User

from tests.conftest import create_address, create_product

pytestmark = pytest.mark.mysql

BACKEND_DIR = Path(__file__).resolve().parents[1]

# V2 引入的表（downgrade 应该全部删掉）
V2_TABLES = {
    "product_skus",
    "banners",
    "favorites",
    "chat_sessions",
    "chat_messages",
    "eval_test_cases",
}
# V1 就有的基础表（downgrade 必须保留——upgrade 里是「缺了才建」，无法区分归属）
BASE_TABLES = {
    "users",
    "addresses",
    "categories",
    "products",
    "cart_items",
    "orders",
    "order_items",
    "knowledge_docs",
}


def _server_and_db_urls():
    """返回 (server_url, db_url, db_name)；未配置 MySQL 时抛 pytest.skip。"""
    explicit = os.environ.get("TEST_MYSQL_URL")
    if explicit:
        db_url = explicit
        db_name = db_url.rsplit("/", 1)[-1].split("?")[0]
    else:
        if not settings.mysql_password:
            pytest.skip("未配置 MYSQL_PASSWORD，跳过 MySQL 集成测试")
        db_name = os.environ.get(
            "TEST_MYSQL_DATABASE", f"{settings.mysql_database}_test"
        )
        db_url = (
            f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}"
            f"@{settings.mysql_host}:{settings.mysql_port}/{db_name}?charset=utf8mb4"
        )

    server_url = db_url.rsplit("/", 1)[0]
    return server_url, db_url, db_name


@pytest.fixture(scope="module")
def mysql_engine():
    server_url, db_url, db_name = _server_and_db_urls()

    try:
        server = create_engine(server_url, isolation_level="AUTOCOMMIT")
        with server.connect() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
        server.dispose()
    except Exception as exc:
        pytest.skip(f"MySQL 不可连接，跳过集成测试: {type(exc).__name__}: {exc}")

    engine = create_engine(
        db_url, pool_size=10, max_overflow=20, pool_pre_ping=True
    )
    Base.metadata.create_all(engine)

    yield engine

    engine.dispose()
    # 只清理自己创建的测试库；万一 TEST_MYSQL_URL 指向了正式库，就只删表不删库
    server = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        if db_name.endswith("_test"):
            conn.execute(text(f"DROP DATABASE IF EXISTS `{db_name}`"))
        else:  # pragma: no cover - 防御性分支
            Base.metadata.drop_all(engine)
    server.dispose()


@pytest.fixture()
def mysql_session(mysql_engine):
    """每个用例一张干净的表结构。"""
    Base.metadata.drop_all(mysql_engine)
    Base.metadata.create_all(mysql_engine)
    Session = sessionmaker(bind=mysql_engine, autocommit=False, autoflush=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_tables_are_innodb(mysql_engine):
    """确认用的确实是 InnoDB——MyISAM 没有行锁，防超卖结论不成立。"""
    with mysql_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'"
            )
        ).all()

    engines = {engine for _name, engine in rows}
    assert rows, "没有建出任何表"
    assert engines == {"InnoDB"}, f"存在非 InnoDB 表: {sorted(engines)}"


def test_foreign_keys_are_enforced(mysql_engine, mysql_session):
    """MySQL 会真正校验外键：删除已被下单的商品会失败。

    这正是不允许物理删除「有订单的商品」的原因；SQLite 默认不校验外键，
    所以那条约束在 SQLite 上是**看不出来**的。
    """
    from sqlalchemy.exc import IntegrityError

    db = mysql_session
    user = User(username="fk_user", password_hash=hash_password("pass1234"))
    db.add(user)
    db.commit()
    db.refresh(user)

    product = create_product(db, "外键商品", skus=[("默认", {}, 100, 5)])
    addr = create_address(db, user)
    from app.services import cart_service, order_service

    cart_service.add_cart_item(db, user, product.id, 1, product.skus[0].id)
    order = order_service.create_order(db, user, addr.id)
    assert order.items

    raw = mysql_engine.connect()
    try:
        with pytest.raises(IntegrityError):
            raw.execute(
                text("DELETE FROM products WHERE id = :pid"), {"pid": product.id}
            )
            raw.commit()
    finally:
        raw.rollback()
        raw.close()


def test_concurrent_orders_no_oversell_on_innodb(mysql_engine, mysql_session):
    """8 个线程并发抢 3 件库存，必须恰好成功 3 单，SKU 与商品库存同时归零。

    与 SQLite 版本的关键区别：这里只有「库存不足」导致的失败才算抢输，
    其他异常一律抛出——否则某个代码 bug 让 5 个线程报错，断言
    ``成功数 == 3`` 依然会通过，测试就变成了假的通过。
    """
    db = mysql_session
    product = create_product(db, "InnoDB 并发商品", skus=[("S", {}, 100, 3)])
    sku_id = product.skus[0].id

    users = []
    for i in range(8):
        u = User(username=f"mysql_race_{i}", password_hash=hash_password("pass1234"))
        db.add(u)
        db.flush()
        users.append(u)

    targets = []
    from app.services import cart_service

    for u in users:
        addr = create_address(db, u)
        cart_service.add_cart_item(db, u, product.id, 1, sku_id)
        targets.append((u.id, addr.id))
    db.commit()

    Session = sessionmaker(bind=mysql_engine, autocommit=False, autoflush=False)

    def place_order(target):
        uid, addr_id = target
        s = Session()
        try:
            from app.services import order_service

            u = s.query(User).filter(User.id == uid).first()
            order_service.create_order(s, u, addr_id)
            return "created"
        except HTTPException as exc:
            s.rollback()
            # 唯一可接受的失败原因
            assert exc.status_code == 400, f"意外的业务错误: {exc.detail}"
            return "sold_out"
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(place_order, targets))

    assert results.count("created") == 3, results
    assert results.count("sold_out") == 5, results

    # 同 test_concurrent_pay_*：先结束本会话的只读事务，否则 REPEATABLE READ
    # 的旧快照会让下面的读取看不到线程里已提交的扣减结果。
    db.rollback()
    assert db.query(ProductSku).filter(ProductSku.id == sku_id).first().stock == 0
    assert db.query(Product).filter(Product.id == product.id).first().stock == 0
    # 库存扣减与订单创建在同一事务里：成功的 3 单各自有明细，失败的一单都没建
    assert db.query(Order).count() == 3
    assert db.query(OrderItem).count() == 3


def test_concurrent_pay_is_idempotent_on_innodb(mysql_engine, mysql_session):
    """同一订单被并发支付多次，只能成功一次，销量只累加一次。"""
    db = mysql_session
    product = create_product(db, "并发支付商品", skus=[("默认", {}, 100, 5)])
    user = User(username="pay_user", password_hash=hash_password("pass1234"))
    db.add(user)
    db.commit()
    db.refresh(user)
    addr = create_address(db, user)

    from app.services import cart_service, order_service

    cart_service.add_cart_item(db, user, product.id, 1, product.skus[0].id)
    order = order_service.create_order(db, user, addr.id)
    order_id = order.id
    assert order.items[0].quantity == 1

    # create_order 内部 commit 会让本会话里的对象过期；必须在起线程之前把
    # 需要的标量取出来，否则工作线程读 user.id 会触发跨线程的惰性加载。
    buyer_id = user.id

    Session = sessionmaker(bind=mysql_engine, autocommit=False, autoflush=False)

    def pay(_):
        s = Session()
        try:
            from app.models.user import User as UserModel

            u = s.query(UserModel).filter(UserModel.id == buyer_id).first()
            order_service.pay_order(s, order_id, u)
            return "paid"
        except HTTPException as exc:
            s.rollback()
            assert exc.status_code == 400, exc.detail
            return "rejected"
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(pay, range(5)))

    assert results.count("paid") == 1, results
    assert results.count("rejected") == 4, results

    # MySQL 默认隔离级别是 REPEATABLE READ：本会话在起线程之前已经读过数据，
    # 那个只读事务的「一致性快照」就固定在了当时的状态，随后即使别的事务提交了
    # 支付结果，本会话再查也仍然看到旧的 pending_pay。必须先结束这个事务
    # （rollback/commit 都行）再断言。SQLite 上不会踩到这个坑，所以这条断言
    # 在 SQLite 版用例里是「碰巧」成立的。
    db.rollback()
    refreshed = db.query(Order).filter(Order.id == order_id).first()
    assert refreshed.status == OrderStatus.PAID
    assert refreshed.paid_at is not None
    # 修复前这里是「先读状态再写」，并发支付会把销量累加多次
    assert db.query(Product).filter(Product.id == product.id).first().sales == 1


# --- 迁移可回滚 ---


def _tables_in(engine) -> set:
    return set(sa_inspect(engine).get_table_names())


def test_alembic_migration_round_trip(monkeypatch):
    """升级 → 回滚到 base → 再升级，必须都能跑通。

    这个迁移原来的 ``downgrade()`` 是 ``pass``：命令成功退出、却什么都没回滚，
    是那种「看起来很安全、真出事时才发现回不去」的状态。

    验证点是三件事：
    1. ``upgrade head`` 之后 V2 的表都在；
    2. ``downgrade base`` 之后 V2 的表全没了，而 V1 的基础表**还在**
       （upgrade 里这些表是「缺了才建」，无法区分归属，宁可少删）；
    3. 再 ``upgrade head`` 能回到同样状态（说明回滚没有留下半截结构）。
    """
    from alembic import command
    from alembic.config import Config

    server_url, _db_url, db_name = _server_and_db_urls()
    scratch = f"{db_name}_migration"

    server = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{scratch}`"))
        conn.execute(
            text(
                f"CREATE DATABASE `{scratch}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )

    # alembic/env.py 是按 settings 现算连接的，所以改库名即可
    monkeypatch.setattr(settings, "mysql_database", scratch)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))

    scratch_engine = create_engine(
        f"{server_url}/{scratch}?charset=utf8mb4", pool_pre_ping=True
    )
    try:
        command.upgrade(config, "head")
        after_upgrade = _tables_in(scratch_engine)
        assert V2_TABLES <= after_upgrade, V2_TABLES - after_upgrade
        assert BASE_TABLES <= after_upgrade

        command.downgrade(config, "base")
        after_downgrade = _tables_in(scratch_engine)
        assert not (V2_TABLES & after_downgrade), V2_TABLES & after_downgrade
        assert BASE_TABLES <= after_downgrade, BASE_TABLES - after_downgrade

        command.upgrade(config, "head")
        assert V2_TABLES <= _tables_in(scratch_engine)
    finally:
        scratch_engine.dispose()
        with server.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS `{scratch}`"))
        server.dispose()
