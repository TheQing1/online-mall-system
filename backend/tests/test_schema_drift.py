"""模型 ↔ 迁移 的 schema 漂移检测。

## 为什么单独写这条

项目里 14 张表由 Alembic 管理，但**测试建表走的是 `Base.metadata.create_all()`**，
不走迁移。于是「迁移建出来的库」和「测试验证的库」是两套 schema，
漂移永远测不出来——功能测试全绿，实际数据库却和模型不一致。

本次真去比对时发现 **10 处差异**，其中两处有真实数据风险：

- `cart_items.sku_id` / `order_items.sku_id` 模型声明了外键，
  而数据库里**没有**——可以写进不存在的 sku_id，订单里留下悬空引用；
- 4 个列在库里允许 NULL，而模型是 NOT NULL。

所以这条测试用 Alembic 官方的 `compare_metadata` 做权威判定，
把「迁移跑出来的真实 schema」和「模型声明」逐项对照。

## 为什么用真实 MySQL 而不是 SQLite

`compare_metadata` 的结果与方言强相关：MySQL 的索引名、枚举类型、
外键默认值、JSON 列的表示都和 SQLite 不同。在 SQLite 上比对，
要么报一堆与本次无关的假差异、要么漏掉真差异。
既然漂移本身就是数据库层面的事，就在真实数据库上验。

连不上 MySQL 时整模块 skip（与 test_mysql_integration.py 一致），CI 不会因此变红。
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.models.base import Base
import app.models  # noqa: F401 —— 注册全部模型，否则 Base.metadata 是空的

pytestmark = pytest.mark.mysql

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _server_url() -> tuple[str, str]:
    """返回 (服务端 URL, 用于测试的库名)，与服务端连接配置对齐。"""
    host = os.environ.get("TEST_MYSQL_HOST", settings.mysql_host)
    port = os.environ.get("TEST_MYSQL_PORT", str(settings.mysql_port))
    user = os.environ.get("TEST_MYSQL_USER", settings.mysql_user)
    password = os.environ.get("TEST_MYSQL_PASSWORD", settings.mysql_password)
    base_db = os.environ.get("TEST_MYSQL_DATABASE", f"{settings.mysql_database}_test")
    server = f"mysql+pymysql://{user}:{password}@{host}:{port}"
    return server, base_db


@pytest.fixture(scope="module")
def migrated_engine():
    """建一个空库，只用 **Alembic 迁移**把它建起来（不用 create_all）。"""
    from sqlalchemy.exc import OperationalError

    server_url, db_name = _server_url()
    scratch = f"{db_name}_drift"

    try:
        server = create_engine(server_url, isolation_level="AUTOCOMMIT")
        with server.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS `{scratch}`"))
            conn.execute(
                text(
                    f"CREATE DATABASE `{scratch}` "
                    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
    except OperationalError as exc:
        pytest.skip(f"没有可用的 MySQL，跳过 schema 漂移检查：{exc}")

    # alembic/env.py 按 settings 现算连接串，改库名即可指向临时库
    original_db = settings.mysql_database
    settings.mysql_database = scratch
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))

    engine = create_engine(f"{server_url}/{scratch}?charset=utf8mb4")

    try:
        command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()
        settings.mysql_database = original_db
        with server.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS `{scratch}`"))
        server.dispose()


def _describe(diff) -> str:
    """把 compare_metadata 的返回项转成可读文本，方便失败时定位。"""
    # 格式不一：有的是元组 ('add_fk', ForeignKeyConstraint(...))，
    # 有的是列表 [('modify_nullable', schema, table, column, ...)]
    if isinstance(diff, list):
        d = diff[0]
        kind = d[0]
        if kind == "modify_nullable":
            return f"modify_nullable: {d[2]}.{d[3]} (库 nullable={d[5]} → 模型 {d[6]})"
        return f"{kind}: {d[1:]}"
    kind = diff[0]
    target = diff[1]
    name = getattr(target, "name", None) or getattr(target, "table", "?")
    return f"{kind}: {name}"


def test_models_match_migrations(migrated_engine):
    """迁移建出来的 schema 必须与模型声明完全一致。

    这里保持「零容忍」（`assert not diffs`）而不是维护一份白名单：
    漂移的成因是两条建库路径不一致，一旦允许例外，例外就会慢慢变多。
    真的需要例外时，先在迁移里把结构改成与模型一致，而不是放宽这个断言。
    """
    with migrated_engine.connect() as conn:
        diffs = compare_metadata(
            MigrationContext.configure(conn), Base.metadata
        )

    report = "\n".join(f"  - {_describe(d)}" for d in diffs)
    assert not diffs, (
        f"模型与迁移存在 {len(diffs)} 处漂移（这就是「测试全绿但库结构不对」"
        f"的来源）：\n{report}\n\n"
        "修复方式：改模型去对齐迁移，或补一条迁移去对齐模型——两者必须选一个，"
        "不能让它们各说各话。"
    )


def test_sku_foreign_keys_are_enforced_on_migrated_schema(migrated_engine):
    """补上的外键必须真的生效，而不只是元数据里「看起来有」。

    这是本次漂移里唯一有真实数据风险的一项：`cart_items.sku_id` /
    `order_items.sku_id` 之前没有外键，可以写进不存在的 SKU。
    这里往真实数据库里插一条悬空引用，断言它被拒绝。
    """
    from sqlalchemy.exc import IntegrityError

    with migrated_engine.begin() as conn:
        # 造一个最小可用的用户（cart_items 需要 user_id 外键）
        conn.execute(
            text(
                "INSERT INTO users (username, password_hash, role, is_active, "
                "created_at, updated_at) VALUES "
                "('drift_probe', 'x', 'user', 1, NOW(), NOW())"
            )
        )
        uid = conn.execute(
            text("SELECT id FROM users WHERE username='drift_probe'")
        ).scalar()

        # 一个不存在的 sku_id 必须被外键拦下
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO cart_items (user_id, product_id, sku_id, quantity, "
                    "created_at, updated_at) VALUES "
                    "(:uid, 999999, 888888, 1, NOW(), NOW())"
                ),
                {"uid": uid},
            )
