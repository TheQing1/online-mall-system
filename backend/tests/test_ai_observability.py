"""AI 链路可观测性（指标 + 结构化日志）的回归测试。

这组用例守的是一个很容易悄悄坏掉的性质：**埋点存在，且埋在了对的分类上**。

指标最典型的失效方式不是报错，而是「代码还在打点，但分类逻辑错了」——
比如把「索引为空」和「召回到但分数不够」都记成同一个 outcome，面板看起来
一切正常，排查时却完全无法区分是该补知识库还是该调阈值。
"""

import asyncio
import logging

from langchain_core.documents import Document
from prometheus_client import REGISTRY


def _counter_value(metric_name: str, **labels) -> float:
    """读取某个指标在指定标签下的当前值（不存在时返回 0）。"""
    value = REGISTRY.get_sample_value(metric_name, labels)
    return value or 0.0


class _Chunk:
    def __init__(self, content, usage=None):
        self.content = content
        self.usage_metadata = usage


class _StubLLM:
    """吐两个 chunk，第二个带 usage_metadata，用来验证 token 计数。"""

    async def astream(self, _prompt):
        yield _Chunk("你好")
        yield _Chunk("，这是回答", usage={"input_tokens": 123, "output_tokens": 45})


# --- 检索结果分类 ---


def test_retrieval_outcome_hit_is_recorded(monkeypatch):
    """有高分命中时，outcome 必须记成 hit。"""
    from app.ai import retriever

    before = _counter_value(
        "rag_retrieval_outcome_total", outcome="hit"
    )
    monkeypatch.setattr(
        retriever,
        "_hybrid_search",
        lambda q, k: [(Document(page_content="退货正文", metadata={"title": "退换货政策"}), 0.9)],
    )
    retriever.retrieve("退货政策", k=3)
    after = _counter_value("rag_retrieval_outcome_total", outcome="hit")

    assert after == before + 1, "命中没被计入 hit"


def test_retrieval_outcome_below_threshold_is_distinguished(monkeypatch):
    """召回到了但分数全低于阈值时，要记 all_below_threshold 而不是 hit。

    这是本组最有价值的一条：这两种情况的处置方式完全不同
    （一个要调阈值/补知识库，一个是正常回答），混在一起面板就看不出问题了。
    """
    from app.ai import retriever
    from app.core.config import settings

    below = settings.rag_min_relevance - 0.1
    monkeypatch.setattr(
        retriever,
        "_hybrid_search",
        lambda q, k: [(Document(page_content="无关内容", metadata={"title": "无关"}), below)],
    )
    before = _counter_value(
        "rag_retrieval_outcome_total", outcome="all_below_threshold"
    )
    retriever.retrieve("完全无关的问题", k=3)
    after = _counter_value(
        "rag_retrieval_outcome_total", outcome="all_below_threshold"
    )

    assert after == before + 1, "低于阈值的召回没有被单独分类"


def test_retrieval_records_best_score_distribution(monkeypatch):
    """top-1 得分要计入分布直方图（用于发现效果漂移）。"""
    from app.ai import retriever

    def _count():
        return _counter_value("rag_best_score_count")

    before = _count()
    monkeypatch.setattr(
        retriever,
        "_hybrid_search",
        lambda q, k: [(Document(page_content="正文", metadata={"title": "标题"}), 0.77)],
    )
    retriever.retrieve("任意问题", k=3)

    assert _count() == before + 1, "top-1 得分没有进入分布统计"


# --- LLM 阶段 ---


def _run_stream(monkeypatch, db, retrieval_hits=None, retrieval_raises=False):
    """跑一遍 generate_stream，返回 (事件, trace)。"""
    from app.ai import rag

    def fake_rewrite(_query, _history, _trace=None):
        return _query

    def fake_retrieve(_query, k=3, mode=None):
        if retrieval_raises:
            raise RuntimeError("检索炸了")
        return retrieval_hits or []

    monkeypatch.setattr(rag, "_rewrite_query", fake_rewrite)
    monkeypatch.setattr(rag, "retrieve", fake_retrieve)
    monkeypatch.setattr(rag.product_service, "search_products", lambda *a, **k: [])
    monkeypatch.setattr(rag, "get_llm", lambda **kw: _StubLLM())

    trace = rag.ChatTrace()
    events = []

    async def scenario():
        async for event in rag.generate_stream(db, "sess-x", "问题", trace):
            events.append(event)

    asyncio.run(scenario())
    return events, trace


def test_generate_stream_records_tokens_and_ttft(monkeypatch, db):
    """token 消耗与首 token 延迟都要落到 trace 上，否则算不出成本也看不出体感。"""
    events, trace = _run_stream(
        monkeypatch,
        db,
        retrieval_hits=[
            (Document(page_content="退货正文", metadata={"title": "退换货政策"}), 0.9)
        ],
    )

    assert any(e.text for e in events), "没有产出文本"
    assert trace.prompt_tokens == 123
    assert trace.completion_tokens == 45
    assert trace.ttft_ms > 0, "首 token 延迟没有记录"
    assert trace.total_ms > 0
    assert trace.hit_count == 1
    assert trace.product_fallback is False


def test_token_counter_increases(monkeypatch, db):
    """token 要真正累加到 Prometheus 计数器上（成本曲线靠它）。"""
    before = _counter_value("llm_tokens_total", kind="prompt")
    _run_stream(
        monkeypatch,
        db,
        retrieval_hits=[
            (Document(page_content="正文", metadata={"title": "标题"}), 0.9)
        ],
    )
    after = _counter_value("llm_tokens_total", kind="prompt")
    assert after == before + 123


def test_product_fallback_is_recorded(monkeypatch, db):
    """没命中知识库、改走商品兜底时，要记一次降级。"""
    before = _counter_value("rag_stage_fallback_total", stage="product_fallback")
    _events, trace = _run_stream(monkeypatch, db, retrieval_hits=[])

    assert trace.product_fallback is True
    assert _counter_value("rag_stage_fallback_total", stage="product_fallback") == before + 1


def test_llm_error_is_recorded(monkeypatch, db):
    """生成阶段抛异常时，要记错误分类并让 trace 带上 error。"""
    from app.ai import rag

    class _BoomLLM:
        async def astream(self, _prompt):
            raise RuntimeError("模型挂了")
            yield  # pragma: no cover

    monkeypatch.setattr(rag, "_rewrite_query", lambda q, h, t=None: q)
    monkeypatch.setattr(rag, "retrieve", lambda q, k=3, mode=None: [])
    monkeypatch.setattr(rag.product_service, "search_products", lambda *a, **k: [])
    monkeypatch.setattr(rag, "get_llm", lambda **kw: _BoomLLM())

    before = _counter_value("rag_stage_fallback_total", stage="llm_error")
    trace = rag.ChatTrace()
    events = []

    async def scenario():
        async for event in rag.generate_stream(db, "sess-y", "问题", trace):
            events.append(event)

    asyncio.run(scenario())

    assert trace.error == "RuntimeError"
    assert _counter_value("rag_stage_fallback_total", stage="llm_error") == before + 1
    # 错误帧要照常推给前端，用户能看到提示
    assert any("暂时不可用" in (e.text or "") for e in events)


# --- 结构化日志 ---


def test_json_formatter_passes_through_business_fields():
    """JsonFormatter 必须透传 extra 里的业务字段。

    修复前它只白名单了 method/path/status/duration_ms，AI 链路的
    retrieval_ms / ttft_ms / prompt_tokens 会被静默丢弃——埋点了也看不到。
    """
    from app.core.logging_config import JsonFormatter
    import json

    record = logging.LogRecord(
        name="app.ai", level=logging.INFO, pathname=__file__, lineno=1,
        msg="AI 对话完成", args=(), exc_info=None,
    )
    record.request_id = "abc123"
    record.retrieval_ms = 38.5
    record.ttft_ms = 1100.0
    record.prompt_tokens = 812
    record.hit_count = 3

    payload = json.loads(JsonFormatter().format(record))

    assert payload["retrieval_ms"] == 38.5
    assert payload["ttft_ms"] == 1100.0
    assert payload["prompt_tokens"] == 812
    assert payload["hit_count"] == 3
    assert payload["request_id"] == "abc123"


# --- label 基数防护 ---


def test_route_label_normalizes_unmatched_paths():
    """404 等未匹配路径必须被归一化，不能把原始路径当 label。

    修复前 ``return path or scope.get("path")`` 会让每个随机地址都变成
    一条新时间序列，未认证就能打爆 Prometheus。
    """
    from app.core.metrics import route_label

    a = route_label({"path": "/api/v1/products/abc123"})
    b = route_label({"path": "/api/v1/products/zzz999"})
    c = route_label({"path": "/completely/random/deep/path/xyz"})

    assert a == b, "不同商品 id 应当归一到同一个 label"
    assert "abc123" not in a and "zzz999" not in b
    assert "random" not in c or "xyz" not in c

    # 路由模板仍然优先
    class _Route:
        path = "/api/v1/products/{product_id}"

    assert route_label({"route": _Route(), "path": "/api/v1/products/1"}) == (
        "/api/v1/products/{product_id}"
    )
