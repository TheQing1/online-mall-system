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
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    specs = Column(JSON, default=dict, nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)
    stock = Column(Integer, default=0, nullable=False)

    product = relationship("Product", back_populates="skus")
