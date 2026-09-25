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
    pass
