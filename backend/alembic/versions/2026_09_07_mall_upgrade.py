"""v2 upgrade: sku / favorites / banners / chat / eval / order lifecycle

Revision ID: 2026_09_07_0001
Revises:
Create Date: 2026-09-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "2026_09_07_0001"
down_revision = None
branch_labels = None
depends_on = None


ORDER_STATUSES = (
    "PENDING_PAY",
    "PAID",
    "SHIPPED",
    "COMPLETED",
    "CANCELLED",
    "REFUNDING",
    "REFUNDED",
)
PRODUCT_STATUSES = ("ON", "OFF")
USER_ROLES = ("USER", "ADMIN")
KNOWLEDGE_CATEGORIES = ("PRODUCT", "ORDER", "REFUND", "OTHER")


def _table_exists(conn, name):
    return name in inspect(conn).get_table_names()


def _column_exists(conn, table, column):
    return any(c["name"] == column for c in inspect(conn).get_columns(table))


def _table(conn):
    bind = conn.get_bind()
    return bind


def _create_table_if_missing(conn, name, *columns):
    if _table_exists(conn, name):
        return
    op.create_table(name, *columns)


def _add_column_if_missing(conn, table, column_obj):
    if not _column_exists(conn, table, column_obj.name):
        op.add_column(table, column_obj)


def upgrade():
    conn = op.get_bind()

    # ---- 基础表（兼容全新/已有库） ----
    if not _table_exists(conn, "users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("username", sa.String(50), nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("email", sa.String(100), nullable=True),
            sa.Column("phone", sa.String(20), nullable=True),
            sa.Column("avatar", sa.String(255), nullable=True),
            sa.Column("role", sa.Enum(*USER_ROLES, name="userrole"), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.UniqueConstraint("username"),
        )

    if not _table_exists(conn, "categories"):
        op.create_table(
            "categories",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(50), nullable=False),
            sa.Column(
                "parent_id",
                sa.Integer(),
                sa.ForeignKey("categories.id"),
                nullable=True,
            ),
            sa.Column("sort", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )

    if not _table_exists(conn, "products"):
        op.create_table(
            "products",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("price", sa.DECIMAL(10, 2), nullable=False),
            sa.Column("stock", sa.Integer(), nullable=False),
            sa.Column("images", sa.JSON(), nullable=False),
            sa.Column(
                "status",
                sa.Enum(*PRODUCT_STATUSES, name="productstatus"),
                nullable=False,
            ),
            sa.Column("sales", sa.Integer(), nullable=False),
            sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )

    if not _table_exists(conn, "knowledge_docs"):
        op.create_table(
            "knowledge_docs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column(
                "category",
                sa.Enum(*KNOWLEDGE_CATEGORIES, name="knowledgecategory"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )

    if not _table_exists(conn, "addresses"):
        op.create_table(
            "addresses",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("receiver", sa.String(50), nullable=False),
            sa.Column("phone", sa.String(20), nullable=False),
            sa.Column("province", sa.String(50), nullable=False),
            sa.Column("city", sa.String(50), nullable=False),
            sa.Column("district", sa.String(50), nullable=False),
            sa.Column("detail", sa.Text(), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )

    # ---- 新增表 ----
    _create_table_if_missing(
        conn,
        "product_skus",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("specs", sa.JSON(), nullable=False),
        sa.Column("price", sa.DECIMAL(10, 2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("product_id", "name", name="uq_product_sku_name"),
    )

    _create_table_if_missing(
        conn,
        "banners",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("image", sa.String(255), nullable=False),
        sa.Column("link", sa.String(255), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    _create_table_if_missing(
        conn,
        "favorites",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "product_id", name="uq_favorite_user_product"),
    )

    _create_table_if_missing(
        conn,
        "chat_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    _create_table_if_missing(
        conn,
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("chat_sessions.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    _create_table_if_missing(
        conn,
        "eval_test_cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_title", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # ---- orders / order_items 新列 ----
    if not _table_exists(conn, "orders"):
        op.create_table(
            "orders",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("order_no", sa.String(32), nullable=False),
            sa.Column("total_amount", sa.DECIMAL(10, 2), nullable=False),
            sa.Column(
                "status",
                sa.Enum(*ORDER_STATUSES, name="orderstatus"),
                nullable=False,
            ),
            sa.Column("address_snapshot", sa.JSON(), nullable=False),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("refund_from_status", sa.String(20), nullable=True),
            sa.Column("refund_reason", sa.Text(), nullable=True),
            sa.Column("refund_note", sa.Text(), nullable=True),
            sa.Column("refunded_at", sa.DateTime(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.UniqueConstraint("order_no"),
        )
    else:
        _add_column_if_missing(
            conn, "orders", sa.Column("paid_at", sa.DateTime(), nullable=True)
        )
        _add_column_if_missing(
            conn,
            "orders",
            sa.Column("refund_from_status", sa.String(20), nullable=True),
        )
        _add_column_if_missing(
            conn, "orders", sa.Column("refund_reason", sa.Text(), nullable=True)
        )
        _add_column_if_missing(
            conn, "orders", sa.Column("refund_note", sa.Text(), nullable=True)
        )
        _add_column_if_missing(
            conn, "orders", sa.Column("refunded_at", sa.DateTime(), nullable=True)
        )

    if not _table_exists(conn, "order_items"):
        op.create_table(
            "order_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("sku_id", sa.Integer(), sa.ForeignKey("product_skus.id"), nullable=False),
            sa.Column("sku_name", sa.String(150), nullable=False),
            sa.Column("sku_spec", sa.JSON(), nullable=False),
            sa.Column("product_name", sa.String(200), nullable=False),
            sa.Column("product_image", sa.String(255), nullable=True),
            sa.Column("price", sa.DECIMAL(10, 2), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
    else:
        if not _column_exists(conn, "order_items", "sku_id"):
            op.add_column("order_items", sa.Column("sku_id", sa.Integer(), nullable=True))
        _add_column_if_missing(
            conn, "order_items", sa.Column("sku_name", sa.String(150), nullable=True)
        )
        _add_column_if_missing(
            conn, "order_items", sa.Column("sku_spec", sa.JSON(), nullable=True)
        )

    # ---- cart_items 扩展 ----
    if not _table_exists(conn, "cart_items"):
        op.create_table(
            "cart_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("sku_id", sa.Integer(), sa.ForeignKey("product_skus.id"), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
    else:
        _add_column_if_missing(
            conn, "cart_items", sa.Column("sku_id", sa.Integer(), nullable=True)
        )

    # ---- 老数据回填 SKU ----
    conn.execute(
        text(
            """
            INSERT IGNORE INTO product_skus
                (product_id, name, specs, price, stock, created_at, updated_at)
            SELECT p.id, '默认规格', '{}', p.price, p.stock, NOW(), NOW()
            FROM products p
            WHERE NOT EXISTS (
                SELECT 1 FROM product_skus s WHERE s.product_id = p.id
            )
            """
        )
    )

    if _table_exists(conn, "cart_items"):
        conn.execute(
            text(
                """
                UPDATE cart_items ci
                JOIN (
                    SELECT product_id, MIN(id) AS sku_id
                    FROM product_skus GROUP BY product_id
                ) s ON s.product_id = ci.product_id
                SET ci.sku_id = s.sku_id
                WHERE ci.sku_id IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                DELETE c1 FROM cart_items c1
                JOIN cart_items c2
                  ON c1.user_id = c2.user_id
                 AND c1.sku_id = c2.sku_id
                 AND c1.id > c2.id
                """
            )
        )
        if not any(
            ix["name"] == "uq_cart_user_sku"
            for ix in inspect(conn).get_indexes("cart_items")
        ):
            op.create_unique_constraint(
                "uq_cart_user_sku", "cart_items", ["user_id", "sku_id"]
            )
        try:
            op.alter_column("cart_items", "sku_id", nullable=False)
        except Exception:
            pass

    if _table_exists(conn, "order_items"):
        conn.execute(
            text(
                """
                UPDATE order_items oi
                JOIN (
                    SELECT product_id, MIN(id) AS sku_id
                    FROM product_skus GROUP BY product_id
                ) s ON s.product_id = oi.product_id
                SET oi.sku_id = s.sku_id
                WHERE oi.sku_id IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE order_items oi
                JOIN product_skus s ON s.id = oi.sku_id
                SET oi.sku_name = COALESCE(oi.sku_name, s.name),
                    oi.sku_spec = COALESCE(oi.sku_spec, s.specs)
                """
            )
        )
        try:
            op.alter_column("order_items", "sku_id", nullable=False)
            op.alter_column("order_items", "sku_name", nullable=False)
            op.alter_column("order_items", "sku_spec", nullable=False)
        except Exception:
            pass

    # 索引
    conn = op.get_bind()
    if _table_exists(conn, "orders"):
        inspector = inspect(conn)
        indexes = {ix["name"] for ix in inspector.get_indexes("orders")}
        if "ix_orders_order_no" not in indexes:
            op.create_index("ix_orders_order_no", "orders", ["order_no"])
    if _table_exists(conn, "chat_messages"):
        inspector = inspect(conn)
        indexes = {ix["name"] for ix in inspector.get_indexes("chat_messages")}
        if "ix_chat_messages_session_id" not in indexes:
            op.create_index(
                "ix_chat_messages_session_id", "chat_messages", ["session_id"]
            )


def downgrade():
    """回滚 V2 引入的结构。

    **只回滚 V2 新增的部分，保留基础表**（users / categories / products /
    orders / order_items / cart_items / knowledge_docs / addresses）：
    它们在 V1 就存在，而 upgrade 里是「缺了才建」，所以无法区分某张表到底是
    V1 带来的还是这次迁移建的。宁可少删——多留一张空表不会造成故障，
    删错一张表就是事故。

    顺序上**先删列、再删表**：``order_items.sku_id`` 与 ``cart_items.sku_id``
    都有指向 ``product_skus`` 的外键，不先删列就删不掉表。

    数据不可恢复：SKU、收藏、Banner、会话、评测用例都会丢。
    生产上回滚前必须先备份（``mysqldump``），这一步不该指望迁移自己兜。
    """
    conn = op.get_bind()

    # 每次现查一次（inspector 会缓存反射结果，DDL 之后再用同一个实例会读到旧结构）
    def _index_names(table):
        return {ix["name"] for ix in inspect(conn).get_indexes(table)}

    def _unique_names(table):
        return {c["name"] for c in inspect(conn).get_unique_constraints(table)}

    def _drop_constraints_using(table, columns):
        """删掉引用这些列的外键约束。

        MySQL 不允许在列还被外键引用时直接 DROP COLUMN（报 1828），
        必须先删约束——这一点是真实跑了一遍 round-trip 用例才发现的。
        """
        for fk in inspect(conn).get_foreign_keys(table):
            if set(fk.get("constrained_columns") or ()) & set(columns):
                op.drop_constraint(fk["name"], table, type_="foreignkey")

    # ---- 1) 先删掉指向 V2 表的外键列 ----
    v2_columns = (
        (
            "order_items",
            ("sku_id", "sku_name", "sku_spec"),
        ),
        ("cart_items", ("sku_id",)),
        (
            "orders",
            (
                "paid_at",
                "refund_from_status",
                "refund_reason",
                "refund_note",
                "refunded_at",
            ),
        ),
    )
    for table, columns in v2_columns:
        if not _table_exists(conn, table):
            continue
        _drop_constraints_using(table, columns)
        if table == "cart_items" and "uq_cart_user_sku" in _unique_names(table):
            # InnoDB 的两个约束会互相卡住，顺序必须是：
            #   ① 先补一个 (user_id) 的普通索引 —— 它原本是 user_id 外键的支撑索引，
            #      而这个支撑索引就是下面那个唯一索引（user_id, sku_id）本身；
            #   ② 有了替代索引，才允许删掉唯一约束（否则报 1553）；
            #   ③ 最后才删列。
            # 直接删列也不行：复合唯一索引会退化成 UNIQUE(user_id)，
            # 那等于「一个用户只能有一条购物车记录」，比报错更糟。
            if "ix_cart_items_user_id" not in _index_names(table):
                op.create_index("ix_cart_items_user_id", table, ["user_id"])
            op.drop_constraint("uq_cart_user_sku", table, type_="unique")
        for column in columns:
            if _column_exists(conn, table, column):
                op.drop_column(table, column)

    # ---- 2) 删掉建在基础列上的索引（列本身属于 V1，不删） ----
    if _table_exists(conn, "orders") and "ix_orders_order_no" in _index_names("orders"):
        op.drop_index("ix_orders_order_no", table_name="orders")

    # ---- 3) 删 V2 新增的表：先子表后父表 ----
    for table in (
        "chat_messages",      # 外键指向 chat_sessions
        "chat_sessions",
        "eval_test_cases",
        "favorites",
        "banners",
        "product_skus",       # 最后删：前面已经把引用它的列删干净了
    ):
        if _table_exists(conn, table):
            op.drop_table(table)
