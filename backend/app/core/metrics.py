"""Prometheus 指标。

为什么不用 ``prometheus-fastapi-instrumentator``：它 8.x 要求 ``starlette>=1.0``，
而本项目锁定的 FastAPI 0.115 要求 ``starlette<0.39``——装上直接
``pip check`` 报依赖不一致，应用也起不来。自己实现只要几十行，而且能**复用**
访问日志里已经算好的耗时，不必再包一层中间件重复计时。

一条关键设计：标签用**路由模板**（``/api/v1/products/{product_id}``）而不是原始
路径。用原始路径的话，每个商品 id 都会变成一条独立的时间序列——几千个商品就能把
Prometheus 打爆，这是 label 基数（cardinality）最经典的坑。Starlette 会把匹配到的
路由放进 ``scope["route"]``，这里直接取它的 path。
"""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.responses import Response

http_requests_total = Counter(
    "http_requests_total",
    "HTTP 请求总数",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP 请求耗时（秒）",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# --- 依赖与业务指标 ---
# 光有 HTTP 指标不够：出问题时你要能一眼看出「是 Redis 挂了」「是有人在刷接口」
# 「是定时任务在报错」，而不是只有一条延迟曲线。

redis_up = Gauge(
    "redis_up",
    "Redis 是否可用（1=可用，0=已降级为无缓存/不限流）",
)

cache_operations_total = Counter(
    "cache_operations_total",
    "缓存操作次数",
    ["result"],  # hit / miss / set / negative / error
)

rate_limit_blocked_total = Counter(
    "rate_limit_blocked_total",
    "被限流拒绝的请求数",
    ["scope"],  # api / login / order / chat
)

background_task_runs_total = Counter(
    "background_task_runs_total",
    "定时任务执行次数",
    ["task", "result"],  # result: ok / error / skipped
)

# --- AI / RAG 链路指标 ---
# 交易链路一直有指标，AI 链路却曾经一条都没有：出现「答得慢」「答非所问」
# 「开始胡说」时，只能靠翻日志猜。这一组指标就是为了让下面三个问题变成
# 「看一眼面板就知道」而不是「重启试试」：
#
#   1. 慢在哪？    → 检索耗时 vs 重排耗时 vs LLM 首 token vs 总耗时，四段分开看
#   2. 为什么答不上？→ 结果分类：知识库空 / 全低于阈值 / 兜底商品 / 命中
#   3. 花多少钱？  → token 消耗速率 × 单价

rag_retrieval_duration_seconds = Histogram(
    "rag_retrieval_duration_seconds",
    "RAG 检索耗时（秒，含向量召回 + BM25 融合 + 可选重排）",
    ["mode", "rerank"],  # mode: vector/hybrid × rerank: true/false
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0),
)

rag_retrieval_outcome_total = Counter(
    "rag_retrieval_outcome_total",
    "检索结果分类",
    # hit                    命中且至少一条过阈值（正常路径）
    # empty_index            向量库为空（索引没同步 / 首次启动）
    # all_below_threshold    召回到了，但全部低于相关性阈值
    # no_candidates          向量库非空但一条都没召回
    ["outcome"],
)

rag_best_score = Histogram(
    "rag_best_score",
    "检索 top-1 相关性得分分布（用于发现效果漂移）",
    # 刻意不按 query 打标签：那会把基数打到无穷大。
    # 看的是分布形状——整体左移就说明知识库或模型出问题了。
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

rag_context_chunks = Histogram(
    "rag_context_chunks",
    "最终进入 Prompt 的知识片段条数",
    buckets=(0, 1, 2, 3, 4, 5),
)

rag_rerank_duration_seconds = Histogram(
    "rag_rerank_duration_seconds",
    "交叉编码器重排耗时（秒）",
    buckets=(0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0),
)

llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM 调用耗时（秒）",
    ["stage", "result"],  # stage: rewrite/answer；result: ok/error
    buckets=(0.2, 0.5, 1.0, 2.0, 4.0, 8.0, 15.0, 30.0, 60.0),
)

llm_time_to_first_token_seconds = Histogram(
    "llm_time_to_first_token_seconds",
    "首 token 延迟（秒）——流式体验的真实指标，用户只感知到这个",
    ["stage"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 15.0),
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Token 消耗（成本）",
    ["kind"],  # flag: prompt / completion
)

rag_stage_fallback_total = Counter(
    "rag_stage_fallback_total",
    "AI 链路各阶段的降级次数",
    # rewrite_failed      改写失败，退回原始 query
    # rerank_load_failed  重排模型加载失败，退回召回顺序
    # llm_error           生成阶段异常
    # product_fallback    没用知识库，改走商品兜底
    ["stage"],
)


_UNMATCHED = "__unmatched__"


def route_label(scope) -> str:
    """优先用路由模板；匹配不上（404 等）时**归一化**，绝不回退原始路径。

    这里曾经写成 ``return path or scope.get("path", "unknown")``，即 404 时回退
    到原始请求路径。那等于把上面模块注释里警告的 label 基数问题又放回来了：
    任何一次目录扫描 / 爬虫随机路径，都会在 ``http_requests_total`` 和
    ``http_request_duration_seconds`` 里各生成一条**永久存在**的新时间序列，
    而且未认证就能触发。

    现在只保留前两级路径并显式标记为未匹配：
    ``/api/v1/products/abc123`` → ``/api/v1/products/{unmatched}``，
    各种随机路径都被收敛到有限几个 label 上。
    """
    route = scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return path

    raw = scope.get("path", "") or ""
    segments = [s for s in raw.split("/") if s][:2]
    if not segments:
        return _UNMATCHED
    return "/" + "/".join(segments) + "/{unmatched}"


def observe(method: str, scope, status_code: int, duration_seconds: float) -> None:
    path = route_label(scope)
    http_requests_total.labels(method=method, path=path, status=str(status_code)).inc()
    http_request_duration_seconds.labels(method=method, path=path).observe(
        duration_seconds
    )


def metrics_response() -> Response:
    """Prometheus 文本格式的响应。"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
