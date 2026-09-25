import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.ai.rag import generate_stream
from app.core.database import get_db, get_session_factory
from app.core.deps import get_optional_user
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatMessageOut
from app.schemas.common import MessageResponse
from app.services import chat_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_optional_user),
    db: Session = Depends(get_db),
    session_factory=Depends(get_session_factory),
):
    """AI 客服对话：SSE 流式返回。会话历史持久化，支持多轮。

    归属校验放在开流之前，这样越权访问得到的是正常的 403 状态码，
    而不是被塞进 SSE 流里的错误帧。
    """
    chat_service.get_or_create_session(db, request.session_id, current_user)

    async def event_stream():
        # 刻意不用请求作用域的 db：流式响应会长期持有连接，客户端断连时
        # 依赖注入还可能并发关闭会话。这里在生成器内部自建自关。
        stream_db: Session = session_factory()
        try:
            chat_service.add_message(
                stream_db, request.session_id, "user", request.message, update_title=True
            )
            assistant_parts = []
            async for event in generate_stream(
                stream_db, request.session_id, request.message
            ):
                if event.text is not None:
                    assistant_parts.append(event.text)
                yield event.raw
            # SSE 结束标记
            yield "data: [DONE]\n\n"
            answer = "".join(assistant_parts)
            if answer:
                chat_service.add_message(
                    stream_db, request.session_id, "assistant", answer
                )
        except ValueError as exc:
            # 配置类错误（例如未设置 DEEPSEEK_API_KEY），提示对使用者有意义
            yield f"data: [ERROR] {exc}\n\n"
            yield "data: [DONE]\n\n"
        except Exception:
            # 其他异常记日志，不把内部细节泄露给客户端
            logger.exception("AI 客服流式响应失败")
            yield "data: [ERROR] AI 服务暂时不可用，请稍后再试\n\n"
            yield "data: [DONE]\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def list_messages(
    session_id: str,
    current_user: User = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """会话历史。归属校验在 service 层：他人会话 403，会话不存在 404。"""
    messages = chat_service.list_messages(
        db, session_id, current_user, claim=True
    )
    if messages is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return messages


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    current_user: User = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    ok = chat_service.delete_session(db, session_id, current_user, claim=True)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return MessageResponse(message="已删除会话")
