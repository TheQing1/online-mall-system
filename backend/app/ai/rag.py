"""RAG 流式生成：多轮改写 → 向量检索 → 商品兜底 → LLM 流式输出。

**可观测性**：这条链路原先一行日志、一个指标都没有，导致「答得慢」「答非所问」
根本无从排查——只能重启试试。现在每个阶段都有埋点，一次问答结束后由
``ai_chat`` 打一条结构化日志，把整轮的关键数字串起来（见 ``ChatTrace``）。
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from app.ai.prompts import CHAT_PROMPT
from app.ai.retriever import retrieve
from app.core.config import settings
from app.core.metrics import (
    llm_request_duration_seconds,
    llm_time_to_first_token_seconds,
    llm_tokens_total,
    rag_context_chunks,
    rag_stage_fallback_total,
)
from app.models.product import Product
from app.services import chat_service, product_service

logger = logging.getLogger(__name__)


@dataclass
class ChatTrace:
    """一轮问答的关键数字，供结构化日志使用。

    刻意做成「一个对象一路传」，而不是各阶段各打一条日志：排查时需要把
    「检索够不够好」和「回答慢不慢」放在同一行里对照看，分散在多条日志里
    反而要自己拼。
    """

    rewritten_query: str = ""
    rewrite_ms: float = 0.0
    rewrite_ok: bool = True
    retrieval_ms: float = 0.0
    hit_count: int = 0
    best_score: float = 0.0
    rerank_used: bool = False
    product_fallback: bool = False
    product_count: int = 0
    ttft_ms: float = 0.0
    total_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: Optional[str] = None
    fallbacks: List[str] = field(default_factory=list)

    def as_log_fields(self) -> dict:
        return {
            "rewritten_query": self.rewritten_query,
            "rewrite_ms": round(self.rewrite_ms, 1),
            "rewrite_ok": self.rewrite_ok,
            "retrieval_ms": round(self.retrieval_ms, 1),
            "hit_count": self.hit_count,
            "best_score": round(self.best_score, 3),
            "rerank_used": self.rerank_used,
            "product_fallback": self.product_fallback,
            "product_count": self.product_count,
            "ttft_ms": round(self.ttft_ms, 1),
            "total_ms": round(self.total_ms, 1),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "fallbacks": ",".join(self.fallbacks) or None,
            "error": self.error,
        }


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
        # 让流式响应也带上 usage，否则拿不到 token 数、算不出成本。
        # 它不影响「流式输出」本身，只是让最后一个 chunk 多一个 usage_metadata。
        stream_usage=True,
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


def _rewrite_query(query: str, history: str, trace: Optional[ChatTrace] = None) -> str:
    """把多轮里的省略问句补全成可独立检索的问题。

    失败时**退回原始 query 并记一次降级**——改写只是增强项，不该让整轮失败。
    以前这里是裸 ``except: return query``，静默吞掉，出了问题是查不出来的。
    """
    if not history.strip():
        return query

    started = time.perf_counter()
    try:
        llm = get_llm(temperature=0)
        prompt_value = REWRITE_PROMPT.format(history=history[-1500:], question=query)
        result = llm.invoke(prompt_value)
        rewritten = (result.content or "").strip() or query
        llm_request_duration_seconds.labels(stage="rewrite", result="ok").observe(
            time.perf_counter() - started
        )
        if trace is not None:
            trace.rewrite_ms = (time.perf_counter() - started) * 1000
            trace.rewrite_ok = True
        return rewritten
    except Exception as exc:
        llm_request_duration_seconds.labels(stage="rewrite", result="error").observe(
            time.perf_counter() - started
        )
        rag_stage_fallback_total.labels(stage="rewrite_failed").inc()
        logger.warning("query 改写失败，退回原始问题：%s", exc)
        if trace is not None:
            trace.rewrite_ms = (time.perf_counter() - started) * 1000
            trace.rewrite_ok = False
            trace.fallbacks.append("rewrite_failed")
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
    db: Session, session_id: str, query: str, trace: Optional[ChatTrace] = None
) -> AsyncGenerator[ChatEvent, None]:
    """多轮 RAG 生成；先推商品卡片事件，再流式输出文本。

    ``trace`` 由调用方传入（也可不传），用来把本轮各阶段的数字汇总到一条日志里。
    """
    if trace is None:
        trace = ChatTrace()
    total_started = time.perf_counter()

    history = chat_service.get_history_text(db, session_id, limit=6)
    rewritten = await asyncio.to_thread(_rewrite_query, query, history, trace)
    trace.rewritten_query = rewritten

    # 检索必须是线程，理由和上面的 query 改写一样，但后果更严重：
    # retrieve() 内部是 jieba 分词 → BGE 模型 encode（CPU 前向）→ Chroma 查询
    # →（开启时）CrossEncoder 重排（每条问题约 0.6s）。这些全是同步阻塞调用，
    # 放在事件循环里会让**所有**并发请求一起停顿，包括别人正在进行的 SSE 流
    # 和 /health 探活——这与「用原生 ASGI 中间件保护 SSE 实时性」的初衷相反。
    # 之前只有改写走了线程，检索漏了。
    retrieval_started = time.perf_counter()
    results = await asyncio.to_thread(retrieve, rewritten, 3)
    trace.retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
    trace.rerank_used = settings.rag_rerank_enabled
    trace.best_score = results[0][1] if results else 0.0

    context_parts = []
    for doc, score in results:
        if score >= settings.rag_min_relevance:
            context_parts.append(
                f"【{doc.metadata.get('title', '未知')}】\n{doc.page_content}\n"
            )
    trace.hit_count = len(context_parts)
    rag_context_chunks.observe(len(context_parts))

    products = []
    if not context_parts:
        # 商品兜底检索同样要查库，一并挪进线程
        products = await asyncio.to_thread(
            product_service.search_products, db, rewritten, 3
        )
        trace.product_fallback = True
        trace.product_count = len(products)
        rag_stage_fallback_total.labels(stage="product_fallback").inc()
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
    answer_started = time.perf_counter()
    first_token_at: Optional[float] = None
    try:
        async for chunk in llm.astream(prompt_value):
            # 首 token 延迟才是用户真正感知到的「快不快」，
            # 总耗时里有一大半是模型在吐后面的字。
            if chunk.content and first_token_at is None:
                first_token_at = time.perf_counter()
                ttft = first_token_at - answer_started
                trace.ttft_ms = ttft * 1000
                llm_time_to_first_token_seconds.labels(stage="answer").observe(ttft)
            if chunk.content:
                yield _text_event(chunk.content)

            # stream_usage=True 时，最后一个 chunk 会带 token 用量
            usage = getattr(chunk, "usage_metadata", None)
            if usage:
                trace.prompt_tokens = usage.get("input_tokens") or 0
                trace.completion_tokens = usage.get("output_tokens") or 0

        llm_request_duration_seconds.labels(stage="answer", result="ok").observe(
            time.perf_counter() - answer_started
        )
        if trace.prompt_tokens:
            llm_tokens_total.labels(kind="prompt").inc(trace.prompt_tokens)
        if trace.completion_tokens:
            llm_tokens_total.labels(kind="completion").inc(trace.completion_tokens)
    except Exception as exc:
        llm_request_duration_seconds.labels(stage="answer", result="error").observe(
            time.perf_counter() - answer_started
        )
        rag_stage_fallback_total.labels(stage="llm_error").inc()
        trace.error = type(exc).__name__
        trace.fallbacks.append("llm_error")
        logger.exception("AI 生成阶段失败")
        yield ChatEvent(
            raw=f"data: {json.dumps({'type': 'error', 'content': 'AI 服务暂时不可用，请稍后再试'}, ensure_ascii=False)}\n\n",
            is_text=True,
            text="AI 服务暂时不可用，请稍后再试",
        )
    finally:
        trace.total_ms = (time.perf_counter() - total_started) * 1000
