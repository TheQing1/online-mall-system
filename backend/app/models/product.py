from sqlalchemy import Column, Integer, String, Text, DECIMAL, JSON, Enum, ForeignKey
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base, TimestampMixin


class ProductStatus(str, enum.Enum):
    ON = "on"
    OFF = "off"


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    sort = Column(Integer, default=0, nullable=False)

    products = relationship("Product", back_populates="category")


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 不声明 index=True：商品搜索走的是 `_build_search_filter` 里的
    # LIKE '%kw%' 与 SKU 条件，**前缀通配的 LIKE 用不上 B-tree 索引**，
    # 建了也只是多维护一棵树。这个索引此前只存在于 create_all 建出的库里，
    # 迁移从未创建过——两套建库路径因此对不上。去掉声明让两边一致。
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(DECIMAL(10, 2), nullable=False)
    stock = Column(Integer, default=0, nullable=False)
    images = Column(JSON, default=[], nullable=False)
    status = Column(Enum(ProductStatus), default=ProductStatus.ON, nullable=False)
    sales = Column(Integer, default=0, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    category = relationship("Category", back_populates="products")
    skus = relationship(
        "ProductSku",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductSku.id",
    )
