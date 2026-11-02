from sqlalchemy import Column, Integer, String, DECIMAL, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class ProductSku(Base, TimestampMixin):
    """商品 SKU：规格、独立价格与库存。每个商品至少一个默认 SKU。"""

    __tablename__ = "product_skus"
    __table_args__ = (
        UniqueConstraint("product_id", "name", name="uq_product_sku_name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 刻意不写 index=True：外键列由 InnoDB 自动建索引，而且下面
    # uq_product_sku_name(product_id, name) 的**最左前缀**已经覆盖了
    # 单列 product_id 的查询。模型再声明 index=True，compare_metadata
    # 会报假漂移，照它建索引等于多维护一棵永远不会被用到的 B+ 树。
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    name = Column(String(150), nullable=False)
    specs = Column(JSON, default=dict, nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)
    stock = Column(Integer, default=0, nullable=False)

    product = relationship("Product", back_populates="skus")
