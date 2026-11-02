from sqlalchemy import Column, Integer, String, Boolean, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 只留 unique=True，去掉 index=True：
    # 唯一约束在 MySQL 里本身就带一棵唯一索引（名字就是约束名 username），
    # 再声明 index=True 会让 Alembic 期望一个额外的 ix_users_username，
    # 于是 compare_metadata 报「模型有、库里没有」的假漂移。
    # 同一个结论适用于下面的 email。
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    phone = Column(String(20), nullable=True)
    avatar = Column(String(255), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Use forward references (strings) for models not yet defined
    addresses = relationship(
        "Address", back_populates="user", cascade="all, delete-orphan"
    )
    cart_items = relationship(
        "CartItem", back_populates="user", cascade="all, delete-orphan"
    )
    favorites = relationship(
        "Favorite", back_populates="user", cascade="all, delete-orphan"
    )
    orders = relationship(
        "Order", back_populates="user", cascade="all, delete-orphan"
    )


class Address(Base, TimestampMixin):
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False)
    province = Column(String(50), nullable=False)
    city = Column(String(50), nullable=False)
    district = Column(String(50), nullable=False)
    detail = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="addresses")
