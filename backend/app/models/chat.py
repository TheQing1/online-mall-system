from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class ChatSession(Base, TimestampMixin):
    """AI 客服会话。session_id 由前端生成，未登录用户也能持久化历史。"""

    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True)
    # 刻意不写 index=True：这一列是外键，InnoDB 会**自动**为外键列建索引
    # （实测库里已有名为 user_id 的索引）。模型再声明一次，Alembic 的
    # compare_metadata 就会报「模型有、库里没有」的假漂移，
    # 而按它的建议去建索引只会得到一个功能重复的冗余索引。
    # 同一个结论已经在 alembic/versions/2026_09_08_order_indexes.py 里验证过。
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
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
