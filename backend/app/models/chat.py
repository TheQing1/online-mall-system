from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class ChatSession(Base, TimestampMixin):
    """AI 客服会话。session_id 由前端生成，未登录用户也能持久化历史。"""

    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String(100), default="新会话", nullable=False)

    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base, TimestampMixin):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String(36), ForeignKey("chat_sessions.id"), nullable=False, index=True
    )
    role = Column(String(20), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)

    session = relationship("ChatSession", back_populates="messages")


class EvalTestCase(Base, TimestampMixin):
    """RAG 评测用例：用于后台批量验证检索命中率。"""

    __tablename__ = "eval_test_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(Text, nullable=False)
    expected_title = Column(String(200), nullable=False)
