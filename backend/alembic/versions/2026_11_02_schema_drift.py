"""tighten the constraints that models declare but the database was missing

Revision ID: 2026_11_02_0001
Revises: 2026_09_08_0001
Create Date: 2026-11-02

背景
----
这条迁移不是新功能，而是把「模型声明了、数据库里却不存在」的约束补齐。

为什么会漂移：测试用 ``Base.metadata.create_all()`` 建表，**不走 Alembic**。
于是「迁移建出来的库」和「测试验证的库」是两套 schema，
漂移永远测不出来——只有真去比对才会现形（本次用 ``compare_metadata`` 发现 10 处）。

本迁移处理其中 6 处，按性质分两类：

**A. 缺外键（真实的完整性漏洞）**

``cart_items.sku_id`` 与 ``order_items.sku_id`` 在模型里声明了
``ForeignKey("product_skus.id")``，但数据库里**没有对应外键**。
后果：可以写进一个根本不存在的 sku_id，订单/购物车里留下悬空引用，
而任何依赖「sku 一定存在」的代码都会在后面某处炸掉（且炸点离成因很远）。
这是本次漂移里唯一有真实数据风险的一项。

追加外键前先检查脏数据（有悬空 sku_id 就先清掉），否则 DDL 会直接失败。

**B. 可空性比模型宽松**

| 列 | 库 | 模型 |
|---|---|---|
| ``cart_items.sku_id`` | NULL | NOT NULL |
| ``order_items.sku_id`` | NULL | NOT NULL |
| ``order_items.sku_name`` | NULL | NOT NULL |
| ``order_items.sku_spec`` | NULL | NOT NULL |

这四列的语义上都不该为空：购物车行必然属于某个 SKU；订单项是**下单时的快照**，
没有 sku_name/sku_spec 就无法展示历史订单。库里允许 NULL 只是漏了约束。

收紧前同样先断言「现有数据里没有 NULL」，否则 ALTER 会失败。
本次实测：四列 NULL 均为 0 行，可安全收紧。

降级说明
--------
``downgrade()`` 会**放宽**回可空（可逆），并删掉本迁移加的两个外键。
外键删除前有守卫：只在确认它确实是本迁移建的那个时才删，
避免误删将来可能由别的迁移添加的同名约束。

刻意**没有**做的事
------------------
- 不新建 ``ix_chat_sessions_user_id`` / ``ix_product_skus_product_id``：
  这两列是外键，InnoDB 已自动建索引；``product_skus`` 还额外有
  ``uq_product_sku_name(product_id, name)`` 的最左前缀覆盖。
  报告说「模型有、库里没有」其实是模型不该声明 ``index=True``，
  已在模型侧删掉（见 app/models/chat.py、sku.py 的注释）。
- 不动 ``orders`` 的两个索引：那是反向漂移（迁移建了、模型没声明），
  同样在模型侧补齐，不涉及 DDL。
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy import Integer, String, JSON as SAJSON

revision = "2026_11_02_0001"
down_revision = "2026_09_08_0001"
branch_labels = None
depends_on = None

# 追加外键时用显式名字，方便降级时精确定位
_FK_CART_SKU = "fk_cart_items_sku_id"
_FK_ORDER_SKU = "fk_order_items_sku_id"

# (表, 列, 外键名) —— 需要补外键的两处
_SKU_FKS = (
    ("cart_items", "sku_id", _FK_CART_SKU),
    ("order_items", "sku_id", _FK_ORDER_SKU),
)

# (表, 列, SQLAlchemy 类型) —— 需要收紧为 NOT NULL 的四列。
# 用真实类型对象而不是 sqlalchemy.text()：alter_column 需要能识别类型的对象，
# text() 在 MySQL 上会生成字面量字符串，导致 DDL 语法错误。
_NOT_NULL_COLUMNS = (
    ("cart_items", "sku_id", Integer()),
    ("order_items", "sku_id", Integer()),
    ("order_items", "sku_name", String(150)),
    ("order_items", "sku_spec", SAJSON()),
)

# 迁移多建、模型里没有的两列（OrderItem 不继承 TimestampMixin）
_EXTRA_ORDER_ITEM_COLUMNS = ("created_at", "updated_at")

# 模型声明了 unique=True、迁移却没建的唯一约束
_UQ_USERS_EMAIL = "uq_users_email"


def _table_exists(conn, table: str) -> bool:
    return table in inspect(conn).get_table_names()


def _foreign_keys(conn, table: str) -> dict:
    """{外键名: (列列表, 被引用表)}；表不存在时返回空。"""
    if not _table_exists(conn, table):
        return {}
    return {
        fk["name"]: (list(fk.get("constrained_columns") or []), fk.get("referred_table"))
        for fk in inspect(conn).get_foreign_keys(table)
    }


def _has_sku_fk(conn, table: str, column: str) -> bool:
    """该列是否已经有指向 product_skus 的外键（不管叫什么名字）。"""
    for _name, (cols, referred) in _foreign_keys(conn, table).items():
        if cols == [column] and referred == "product_skus":
            return True
    return False


def _null_count(conn, table: str, column: str) -> int:
    if not _table_exists(conn, table):
        return 0
    return int(
        conn.execute(text(f"SELECT COUNT(*) FROM `{table}` WHERE `{column}` IS NULL")).scalar()
        or 0
    )


def upgrade():
    conn = op.get_bind()

    # --- A. 补外键 ---
    for table, column, fk_name in _SKU_FKS:
        if not _table_exists(conn, table):
            continue
        if _has_sku_fk(conn, table, column):
            continue  # 已经有了（例如新库由 create_all 建成），不重复加

        # 加外键前必须没有悬空引用，否则 ALTER TABLE 会报 1452
        dangling = int(
            conn.execute(
                text(
                    f"SELECT COUNT(*) FROM `{table}` t "
                    f"LEFT JOIN product_skus p ON t.`{column}` = p.id "
                    f"WHERE t.`{column}` IS NOT NULL AND p.id IS NULL"
                )
            ).scalar()
            or 0
        )
        if dangling:
            # 不静默删数据：宁可让迁移失败，也不猜用户想要哪种修复
            raise RuntimeError(
                f"{table}.{column} 有 {dangling} 行指向不存在的 product_skus.id，"
                "请先清理这些悬空引用再重跑迁移"
            )

        # 刻意**不写** ondelete：模型里的 ForeignKey("product_skus.id") 没有指定
        # ondelete 策略，这里跟着保持一致。两条理由：
        #   1. 若写 CASCADE，删除商品会连带删掉购物车行——这对 cart_items 说得通，
        #      但对 order_items 是**危险的**：订单项是下单快照，用户的历史订单
        #      不该因为后来商品被删就消失；
        #   2. 迁移与模型对同一约束的声明必须逐字一致，否则 compare_metadata
        #      会一直报 remove_fk/add_fk 的假漂移。
        # 商品删除在服务层已有明确拦截（见 product_service），不依赖数据库级联。
        op.create_foreign_key(
            fk_name, table, "product_skus", [column], ["id"],
        )

    # --- B. 收紧为 NOT NULL ---
    for table, column, coltype in _NOT_NULL_COLUMNS:
        if not _table_exists(conn, table):
            continue

        n_null = _null_count(conn, table, column)
        if n_null:
            raise RuntimeError(
                f"{table}.{column} 有 {n_null} 行 NULL，无法收紧为 NOT NULL；"
                "请先清洗数据"
            )

        # 已经是 NOT NULL 就跳过（幂等：重复执行不会报错）
        cols = {c["name"]: c for c in inspect(conn).get_columns(table)}
        if column in cols and not cols[column]["nullable"]:
            continue

        op.alter_column(table, column, existing_type=coltype, nullable=False)

    # --- C. 删掉迁移多建、模型里没有的两列 ---
    #
    # `order_items` 在模型里是 `class OrderItem(Base)`，**不继承 TimestampMixin**，
    # 也就是说模型从未声明过 created_at / updated_at；而 2026_09_07 那条迁移
    # 把这两列建了出来。语义上它们也确实多余：订单项的时间就是父订单的时间，
    # 单独记一份只会出现「两张时间对不上」的问题。
    #
    # 以模型为准删掉。这里不检查列里有没有数据——它由 server_default 填 NOW()，
    # 没有任何业务代码写入或读取过，删掉不丢信息。
    for column in _EXTRA_ORDER_ITEM_COLUMNS:
        cols = {c["name"] for c in inspect(conn).get_columns("order_items")}
        if column in cols:
            op.drop_column("order_items", column)

    # --- D. 补上模型声明了、迁移从未建过的唯一约束 ---
    #
    # `users.email` 在模型里是 `unique=True`，但 2026_09_07 的迁移只写了
    # `sa.Column("email", sa.String(100), nullable=True)` —— 普通列，**没有唯一约束**。
    # 当前开发库之所以有，是因为它早期由 create_all 建成；纯迁移建出来的库则没有，
    # 于是「同一邮箱能否重复注册」取决于库是怎么建的，这是最危险的那类不一致。
    #
    # 加约束前先查重复值：有重复时 DDL 会失败，宁可给一条能看懂的报错。
    dup = conn.execute(
        text(
            "SELECT COUNT(*) FROM ("
            "  SELECT email FROM users "
            "  WHERE email IS NOT NULL AND email <> '' "
            "  GROUP BY email HAVING COUNT(*) > 1"
            ") t"
        )
    ).scalar()
    if dup:
        raise RuntimeError(
            f"users.email 有 {dup} 组重复值，无法加唯一约束；请先人工合并这些账号"
        )

    existing_uq = {
        uq["name"] for uq in inspect(conn).get_unique_constraints("users")
    }
    # MySQL 里唯一索引与唯一约束在 information_schema 里表现不同：
    # 若已有同名唯一索引（例如 create_all 建的），也算已满足
    existing_idx = {
        ix["name"]
        for ix in inspect(conn).get_indexes("users")
        if ix.get("unique") and ix["column_names"] == ["email"]
    }
    if _UQ_USERS_EMAIL not in existing_uq and not existing_idx:
        op.create_unique_constraint(_UQ_USERS_EMAIL, "users", ["email"])


def downgrade():
    conn = op.get_bind()

    # 反向 D：删掉本迁移加的唯一约束（守卫：确实存在才删）
    existing_uq = {uq["name"] for uq in inspect(conn).get_unique_constraints("users")}
    if _UQ_USERS_EMAIL in existing_uq:
        op.drop_constraint(_UQ_USERS_EMAIL, "users", type_="unique")

    # 反向 C：把删掉的两列加回来（必须是 NOT NULL + server_default，
    # 否则回滚后的结构无法插入新行）
    for column in _EXTRA_ORDER_ITEM_COLUMNS:
        cols = {c["name"] for c in inspect(conn).get_columns("order_items")}
        if column not in cols:
            op.add_column(
                "order_items",
                sa.Column(column, sa.DateTime(), server_default=sa.func.now(), nullable=False),
            )

    # 反向：放宽回可空（顺序与 upgrade 相反，不出错但更对称）
    for table, column, coltype in reversed(_NOT_NULL_COLUMNS):
        if not _table_exists(conn, table):
            continue
        op.alter_column(table, column, existing_type=coltype, nullable=True)

    # 删掉本迁移加的外键，但只在它确实是我们在 upgrade 里建的那个时才删
    for table, column, fk_name in reversed(_SKU_FKS):
        fks = _foreign_keys(conn, table)
        if fk_name in fks:
            op.drop_constraint(fk_name, table, type_="foreignkey")
