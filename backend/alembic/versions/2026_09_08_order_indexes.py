"""add the order indexes that actually back a query

Revision ID: 2026_09_08_0001
Revises: 2026_09_07_0001
Create Date: 2026-09-08

为什么只有这几个改动
--------------------
审计时曾以为 ``orders.user_id``、``order_items.order_id``、``favorites.user_id``、
``products.category_id`` 等一堆外键列缺索引。实际查过 MySQL
（information_schema.STATISTICS）后发现：**InnoDB 会为每个外键列自动建索引**，
这 13 个外键列全部已被覆盖；``cart_items.user_id`` 也因唯一键
``uq_cart_user_sku`` 的最左前缀而可用。所以这里不重复造索引，只处理三件
经过实测确认的事：

1. 新增 ``ix_orders_status_created_at (status, created_at)``
   后台任务每 30 秒扫一次 ``WHERE status='pending_pay' AND created_at < ?``
   （app/core/tasks.py → order_service.auto_cancel_expired_orders），管理端订单
   列表也按 status 过滤并按 created_at 排序。这条**定时全表扫描**原本没有索引可用。

2. 新增 ``ix_orders_user_id_created_at (user_id, created_at)``，并删掉随之冗余的
   单列 ``user_id``。「我的订单」是 ``WHERE user_id=? ORDER BY created_at DESC``；
   外键自带的 ``(user_id)`` 只能过滤、排序仍需 filesort，联合索引可同时完成两者。
   实测（MySQL 8.0.43）：建了这个联合索引后，InnoDB 会让外键改用它，
   单列 ``user_id`` 索引随之消失——这里显式删除，让结果可预期，
   也保证 downgrade 时能干净还原。

3. 删除冗余的 ``ix_orders_order_no``。
   在由 Alembic 从零建出来的库里，``order_no`` 同时存在两个索引：
   模型里的 ``unique=True`` 生成了唯一索引 ``order_no``，而本仓库上一个迁移看到
   没有叫 ``ix_orders_order_no`` 的索引，又补了一个非唯一的同名索引。
   两者列完全相同，后者纯属多余（每次写入多一次索引维护）。
   **删除前有守卫**：只有确认还存在另一个「单列 + 唯一」的 order_no 索引时才删，
   因此绝不会丢掉唯一性约束；老库（唯一索引本身就叫 ix_orders_order_no）不受影响。

刻意**没有**加的：``orders.created_at`` 单列索引（只服务后台不带筛选的列表页，
性价比低），以及 ``knowledge_docs`` / ``eval_test_cases`` 这类小表的排序索引。
"""

from alembic import op
from sqlalchemy import inspect

revision = "2026_09_08_0001"
down_revision = "2026_09_07_0001"
branch_labels = None
depends_on = None

_STATUS_IDX = "ix_orders_status_created_at"
_USER_IDX = "ix_orders_user_id_created_at"
_ORDER_NO_IDX = "ix_orders_order_no"
_FK_IDX = "user_id"


def _indexes(conn, table: str) -> dict:
    """{索引名: (列列表, 是否唯一)}；表不存在时返回空。"""
    inspector = inspect(conn)
    if table not in inspector.get_table_names():
        return {}
    return {
        ix["name"]: (list(ix.get("column_names") or []), bool(ix.get("unique")))
        for ix in inspector.get_indexes(table)
    }


def upgrade():
    conn = op.get_bind()
    idx = _indexes(conn, "orders")

    if _STATUS_IDX not in idx:
        op.create_index(_STATUS_IDX, "orders", ["status", "created_at"])

    if _USER_IDX not in idx:
        op.create_index(_USER_IDX, "orders", ["user_id", "created_at"])

    # 联合索引已经能支撑外键，显式收敛掉单列 user_id，避免同时留着两个
    idx = _indexes(conn, "orders")
    if _FK_IDX in idx and _USER_IDX in idx:
        op.drop_index(_FK_IDX, table_name="orders")

    # 只有确认还存在另一个「单列 order_no + 唯一」的索引时才删冗余索引
    idx = _indexes(conn, "orders")
    has_unique_order_no = any(
        name != _ORDER_NO_IDX and cols == ["order_no"] and unique
        for name, (cols, unique) in idx.items()
    )
    if _ORDER_NO_IDX in idx and has_unique_order_no:
        op.drop_index(_ORDER_NO_IDX, table_name="orders")


def downgrade():
    """真实可用的回滚：把 orders 的索引恢复到本迁移之前的样子。

    关键点：必须先重建单列 ``user_id`` 索引，再删联合索引。
    外键 ``orders_ibfk_1`` 依赖索引，直接删联合索引会报
    MySQL 1553「Cannot drop index ... needed in a foreign key constraint」。
    """
    conn = op.get_bind()
    idx = _indexes(conn, "orders")

    if _FK_IDX not in idx:
        op.create_index(_FK_IDX, "orders", ["user_id"])

    idx = _indexes(conn, "orders")
    if _USER_IDX in idx:
        op.drop_index(_USER_IDX, table_name="orders")
    if _STATUS_IDX in idx:
        op.drop_index(_STATUS_IDX, table_name="orders")

    idx = _indexes(conn, "orders")
    if _ORDER_NO_IDX not in idx and "order_no" in idx:
        op.create_index(_ORDER_NO_IDX, "orders", ["order_no"])
