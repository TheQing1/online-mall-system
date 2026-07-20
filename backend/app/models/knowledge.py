from sqlalchemy import Column, Integer, String, Text, Enum
import enum

from app.models.base import Base, TimestampMixin


class KnowledgeCategory(str, enum.Enum):
    PRODUCT = "product"
    ORDER = "order"
    REFUND = "refund"
    OTHER = "other"


class KnowledgeDoc(Base, TimestampMixin):
    __tablename__ = "knowledge_docs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(
        Enum(KnowledgeCategory), default=KnowledgeCategory.OTHER, nullable=False
    )
