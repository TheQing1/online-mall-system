from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.core.deps import get_optional_user
from app.ai.rag import generate_stream
import traceback

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
async def chat(request: ChatRequest, current_user=Depends(get_optional_user)):
    """AI 客服对话接口 — SSE 流式返回"""
    async def event_stream():
        try:
            async for text in generate_stream(request.message):
                yield f"data: {text}\n\n"
            yield "data: [DONE]\n\n"
        except ValueError as e:
            yield f"data: [ERROR] {str(e)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            msg = str(e) or type(e).__name__
            traceback.print_exc()
            yield f"data: [ERROR] {msg}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
