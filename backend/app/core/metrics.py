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

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
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


def route_label(scope) -> str:
    """优先用路由模板；匹配不上（404）时退回原始路径。"""
    route = scope.get("route")
    path = getattr(route, "path", None)
    return path or scope.get("path", "unknown")


def observe(method: str, scope, status_code: int, duration_seconds: float) -> None:
    path = route_label(scope)
    http_requests_total.labels(method=method, path=path, status=str(status_code)).inc()
    http_request_duration_seconds.labels(method=method, path=path).observe(
        duration_seconds
    )


def metrics_response() -> Response:
    """Prometheus 文本格式的响应。"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
