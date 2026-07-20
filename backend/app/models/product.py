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
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(DECIMAL(10, 2), nullable=False)
    stock = Column(Integer, default=0, nullable=False)
    images = Column(JSON, default=[], nullable=False)
    status = Column(Enum(ProductStatus), default=ProductStatus.ON, nullable=False)
    sales = Column(Integer, default=0, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    category = relationship("Category", back_populates="products")
