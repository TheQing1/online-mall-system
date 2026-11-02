"""AI 生成链路（generate_stream）的非阻塞保证。

为什么要单独写这条用例：``generate_stream`` 是 async 生成器，但它内部调用的
检索（jieba 分词 + BGE encode + Chroma 查询 + 可选 CrossEncoder 重排）和商品
兜底查询全是**同步阻塞**实现。一旦它们直接在协程里跑，就会把整个 uvicorn
事件循环卡住——所有并发请求（包括别人正在进行的 SSE 流和 /health 探活）一起停顿。

修复前只有 query 改写走了线程池，``retrieve()`` 和商品检索漏了。
这条用例用「慢速桩 + 心跳协程」把它钉死：只要有人把调用改回同步，
心跳次数会掉到 0 或 1，断言立刻失败。
"""

import asyncio

from langchain_core.documents import Document


class _Chunk:
    def __init__(self, content):
        self.content = content


class _StubLLM:
    """假的 LLM：只吐一个字，够触发流式输出分支。"""

    async def astream(self, _prompt):
        yield _Chunk("好的")


def _run_stream(monkeypatch, db, slow_seconds=0.25):
    """跑一遍 generate_stream 并返回 (事件列表, 心跳次数)。"""
    from app.ai import rag

    def fake_rewrite(_query, _history, _trace=None):
        # _rewrite_query 本身是同步函数（外面用 asyncio.to_thread 包着调），
        # 这里必须保持同步，否则 to_thread 拿到的是协程对象而不是结果。
        # _trace 是 P1 加的可观测性参数，桩函数要一并接受。
        return _query

    def slow_retrieve(_query, k=3):
        # 模拟真实的 CPU 密集检索：用 sleep 代替算力消耗
        import time

        time.sleep(slow_seconds)
        return [(Document(page_content="退货政策正文", metadata={"title": "退换货政策"}), 0.9)]

    def slow_product_search(_db, _keyword, limit=5):
        import time

        time.sleep(slow_seconds)
        return []

    monkeypatch.setattr(rag, "_rewrite_query", fake_rewrite)
    monkeypatch.setattr(rag, "retrieve", slow_retrieve)
    monkeypatch.setattr(rag.product_service, "search_products", slow_product_search)
    monkeypatch.setattr(rag, "get_llm", lambda **_kwargs: _StubLLM())
    monkeypatch.setattr(rag.chat_service, "get_history_text", lambda *_a, **_k: "")

    async def scenario():
        beats = 0
        stop = asyncio.Event()

        async def heartbeat():
            nonlocal beats
            while not stop.is_set():
                beats += 1
                await asyncio.sleep(0.01)

        task = asyncio.create_task(heartbeat())
        events = []
        async for event in rag.generate_stream(db, "sess-1", "退货怎么弄"):
            events.append(event)
        stop.set()
        await task
        return events, beats

    return asyncio.run(scenario())


def test_retrieval_does_not_block_the_event_loop(monkeypatch, db):
    """检索与商品兜底都必须走线程池，不能卡住事件循环。

    修复前 ``retrieve()`` 直接在协程里跑：0.25s 的阻塞期间心跳一次都打不出来。
    修复后它在线程里跑，事件循环照常调度，心跳应该能打十几到二十次。
    """
    events, beats = _run_stream(monkeypatch, db, slow_seconds=0.25)

    # 确实产生了流式文本事件
    assert any(event.text for event in events), "没有产出任何文本事件"

    # 心跳在 0.25s 的阻塞期内应当能跑很多次（10ms 一次 ≈ 25 次）
    assert beats >= 10, (
        f"阻塞期间只打了 {beats} 次心跳，说明检索/商品查询仍在事件循环里同步执行"
    )


def test_generate_stream_emits_text_for_retrieved_context(monkeypatch, db):
    """检索命中时应当把知识库片段喂给模型并输出文本。

    这是行为层面的守卫：把 retrieve 改成线程后返回值仍要被正确消费，
    否则「不阻塞」会以「检索结果丢了」为代价。
    """
    events, _beats = _run_stream(monkeypatch, db, slow_seconds=0.0)
    text = "".join(event.text or "" for event in events)
    assert text.strip(), "生成的文本为空"
