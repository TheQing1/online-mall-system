"""RAG 流式生成：多轮改写 → 向量检索 → 商品兜底 → LLM 流式输出。"""

import asyncio
import json
from dataclasses import dataclass
from typing import AsyncGenerator, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from app.ai.prompts import CHAT_PROMPT
from app.ai.retriever import retrieve
from app.core.config import settings
from app.models.product import Product
from app.services import chat_service, product_service


@dataclass
class ChatEvent:
    raw: str
    is_text: bool = True
    text: Optional[str] = None


def _text_event(content: str) -> ChatEvent:
    return ChatEvent(
        raw=f"data: {json.dumps({'type': 'text', 'content': content}, ensure_ascii=False)}\n\n",
        is_text=True,
        text=content,
    )


def get_llm(model: Optional[str] = None, temperature: float = 0.7) -> ChatOpenAI:
    if not settings.deepseek_api_key or settings.deepseek_api_key == "your-deepseek-api-key":
        raise ValueError("请先在 .env 中配置 DEEPSEEK_API_KEY")
    return ChatOpenAI(
        model=model or settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        streaming=True,
        temperature=temperature,
    )


REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是对话改写助手。请结合对话历史，把用户最新提问改写为独立、完整、可直接检索的中文问题。"
            "如果问题已经完整清晰，直接原样输出。只输出改写后的问题，不要解释。",
        ),
        ("human", "对话历史：\n{history}\n\n最新提问：{question}"),
    ]
)


def _rewrite_query(query: str, history: str) -> str:
    if not history.strip():
        return query
    try:
        llm = get_llm(temperature=0)
        prompt_value = REWRITE_PROMPT.format(history=history[-1500:], question=query)
        result = llm.invoke(prompt_value)
        rewritten = (result.content or "").strip()
        return rewritten if rewritten else query
    except Exception:
        return query


def _format_products(products: List[Product]) -> str:
    lines = []
    for p in products:
        price = min(sku.price for sku in p.skus) if p.skus else p.price
        lines.append(f"- {p.name}，价格 ¥{price}，销量 {p.sales}，简介：{(p.description or '')[:120]}")
    return "\n".join(lines)


def _product_events(products: List[Product]) -> List[ChatEvent]:
    payload = []
    for p in products:
        payload.append(
            {
                "id": p.id,
                "name": p.name,
                "price": float(min(sku.price for sku in p.skus) if p.skus else p.price),
                "image": p.images[0] if p.images else "",
                "sales": p.sales,
            }
        )
    return [
        ChatEvent(
            raw=f"data: {json.dumps({'type': 'products', 'items': payload}, ensure_ascii=False)}\n\n",
            is_text=False,
        )
    ]


async def generate_stream(
    db: Session, session_id: str, query: str
) -> AsyncGenerator[ChatEvent, None]:
    """多轮 RAG 生成；先推商品卡片事件，再流式输出文本。"""
    history = chat_service.get_history_text(db, session_id, limit=6)
    rewritten = await asyncio.to_thread(_rewrite_query, query, history)

    results = retrieve(rewritten, k=3)
    context_parts = []
    for doc, score in results:
        if score >= settings.rag_min_relevance:
            context_parts.append(
                f"【{doc.metadata.get('title', '未知')}】\n{doc.page_content}\n"
            )

    products = []
    if not context_parts:
        products = product_service.search_products(db, rewritten, limit=3)
        for event in _product_events(products):
            yield event

    context = "\n".join(context_parts) if context_parts else "暂无相关知识库信息"
    product_context = _format_products(products) if products else ""

    instruction = (
        "用户询问与商品相关的内容，你可以结合下方商品库信息推荐商品；"
        "请用简洁友好的语气回复。"
        if products
        else "如果知识库没有相关信息，请礼貌告知无法回答，并建议用户联系人工客服。"
    )
    prompt_value = CHAT_PROMPT.format(
        context=context,
        product_context=product_context,
        instruction=instruction,
        question=query,
    )

    llm = get_llm()
    try:
        async for chunk in llm.astream(prompt_value):
            if chunk.content:
                yield _text_event(chunk.content)
    except Exception:
        yield ChatEvent(
            raw=f"data: {json.dumps({'type': 'error', 'content': 'AI 服务暂时不可用，请稍后再试'}, ensure_ascii=False)}\n\n",
            is_text=True,
            text="AI 服务暂时不可用，请稍后再试",
        )
