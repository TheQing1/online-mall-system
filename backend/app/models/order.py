from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DECIMAL,
    JSON,
    Enum,
    ForeignKey,
    DateTime,
    Index,
)
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base, TimestampMixin


class OrderStatus(str, enum.Enum):
    PENDING_PAY = "pending_pay"
    PAID = "paid"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDING = "refunding"
    REFUNDED = "refunded"


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    # 这两个索引原先**只存在于迁移里、模型中没有声明**。
    # 后果是：`alembic upgrade head` 建出来的库有索引，但如果有人用
    # `Base.metadata.create_all()`（测试就是这么建表的）建库就会丢掉它们——
    # 于是「测试跑得飞快、生产却很慢」，而且 compare_metadata 会一直报
    # 「库里有、模型没有」的反向漂移。
    # 声明放在模型里，两条建库路径才对同一份 schema 负责。
    __table_args__ = (
        # 关单任务每 30 秒扫一次 WHERE status='pending_pay' AND created_at < ?
        Index("ix_orders_status_created_at", "status", "created_at"),
        # 「我的订单」是 WHERE user_id=? ORDER BY created_at DESC
        Index("ix_orders_user_id_created_at", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # 只留 unique=True，不写 index=True：唯一约束自带索引。
    # 迁移里建的名字是 order_no（MySQL 用约束名命名索引）；
    # 若在这里再声明 index=True，Alembic 会期望 ix_orders_order_no，
    # 与实际库不一致，compare_metadata 会一直报索引改名。
    order_no = Column(String(32), unique=True, nullable=False)
    total_amount = Column(DECIMAL(10, 2), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING_PAY, nullable=False)
    address_snapshot = Column(JSON, nullable=False)
    remark = Column(Text, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    refund_from_status = Column(String(20), nullable=True)
    refund_reason = Column(Text, nullable=True)
    refund_note = Column(Text, nullable=True)
    refunded_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="orders")
    items = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    sku_id = Column(Integer, ForeignKey("product_skus.id"), nullable=False)
    sku_name = Column(String(150), nullable=False)
    sku_spec = Column(JSON, nullable=False, default=dict)
    product_name = Column(String(200), nullable=False)
    product_image = Column(String(255), nullable=True)
    price = Column(DECIMAL(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")
    sku = relationship("ProductSku")
