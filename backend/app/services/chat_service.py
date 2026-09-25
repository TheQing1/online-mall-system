from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession


def get_accessible_session(
    db: Session,
    session_id: str,
    user=None,
    *,
    claim: bool = False,
) -> Optional[ChatSession]:
    """按 session_id 取会话，并校验调用方是否有权访问。

    会话归属规则：
    - 已绑定用户的会话（``user_id`` 非空）：只有该用户本人可以访问，否则 403；
    - 匿名会话（``user_id`` 为空）：AI 客服允许未登录使用，因此仅靠 UUID 的
      不可猜测性保护；登录用户访问时会把会话「认领」到自己名下（``claim=True``），
      这样先匿名聊天再登录时历史不会丢失。

    返回 ``None`` 表示会话不存在（调用方应返回 404）。
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session is None:
        return None

    if session.user_id is None:
        if claim and user is not None:
            session.user_id = user.id
            db.commit()
            db.refresh(session)
        return session

    if user is not None and session.user_id == user.id:
        return session

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该会话"
    )


def get_or_create_session(db: Session, session_id: str, user=None) -> ChatSession:
    session = get_accessible_session(db, session_id, user, claim=True)
    if session is not None:
        return session
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
    # created_at 只到秒，同一秒内的消息顺序不确定，用 id 兜底保证稳定
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
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


def list_messages(
    db: Session, session_id: str, user=None, *, claim: bool = False
) -> Optional[List[ChatMessage]]:
    """列出会话消息；会话不存在返回 None，无权限抛 403。"""
    if get_accessible_session(db, session_id, user, claim=claim) is None:
        return None
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )


def delete_session(
    db: Session, session_id: str, user=None, *, claim: bool = False
) -> bool:
    """删除会话；不存在返回 False，无权限抛 403。"""
    session = get_accessible_session(db, session_id, user, claim=claim)
    if session is None:
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
