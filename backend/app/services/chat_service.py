from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession


def get_or_create_session(db: Session, session_id: str, user=None) -> ChatSession:
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        session = ChatSession(
            id=session_id,
            user_id=user.id if user else None,
            title="新会话",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def get_history(db: Session, session_id: str, limit: int = 8) -> List[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()[::-1]
    )


def get_history_text(db: Session, session_id: str, limit: int = 6) -> str:
    messages = get_history(db, session_id, limit)
    lines = []
    for msg in messages:
        role = "用户" if msg.role == "user" else "客服"
        lines.append(f"{role}: {msg.content[:300]}")
    return "\n".join(lines)


def list_messages(db: Session, session_id: str):
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


def delete_session(db: Session, session_id: str) -> bool:
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        return False
    db.delete(session)
    db.commit()
    return True


def add_message(
    db: Session, session_id: str, role: str, content: str, update_title=False
) -> ChatMessage:
    message = ChatMessage(session_id=session_id, role=role, content=content)
    db.add(message)
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session:
        session.updated_at = datetime.now()
    if update_title and content.strip():
        title = content.strip().replace("\n", " ")[:20]
        if session and (not session.title or session.title == "新会话"):
            session.title = title
    db.commit()
    return message


def list_user_sessions(db: Session, user) -> List[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
