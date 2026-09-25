from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.ai.rag import generate_stream
from app.core.database import SessionLocal
from app.core.deps import get_optional_user
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatMessageOut
from app.services import chat_service

router = APIRouter()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_optional_user),
):
    """AI 客服对话：SSE 流式返回。会话历史持久化，支持多轮。"""

    async def event_stream():
        db = SessionLocal()
        try:
            chat_service.get_or_create_session(
                db, request.session_id, current_user
            )
            chat_service.add_message(
                db, request.session_id, "user", request.message, update_title=True
            )
            assistant_parts = []
            async for event in generate_stream(db, request.session_id, request.message):
                if event.text is not None:
                    assistant_parts.append(event.text)
                yield event.raw
            # SSE 结束标记
            yield "data: [DONE]\n\n"
            answer = "".join(assistant_parts)
            if answer:
                chat_service.add_message(
                    db, request.session_id, "assistant", answer
                )
        except ValueError as e:
            yield f"data: [ERROR] {e}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {e}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            db.close()

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
    _: User = Depends(get_optional_user),
):
    db = SessionLocal()
    try:
        return chat_service.list_messages(db, session_id)
    finally:
        db.close()


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    _: User = Depends(get_optional_user),
):
    from app.schemas.common import MessageResponse

    db = SessionLocal()
    try:
        chat_service.delete_session(db, session_id)
        return MessageResponse(message="已删除会话")
    finally:
        db.close()
