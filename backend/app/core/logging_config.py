"""结构化日志、请求 ID 与访问日志。

目标只有一个：出问题时能把**一次请求**的日志串起来。

- 每条日志带 ``request_id``；优先复用上游（nginx）传来的 ``X-Request-ID``，没有就生成；
- 响应头回写 ``X-Request-ID``，用户报障时能直接给出这个 ID；
- 慢请求单独打一条 warning，用来揪出「不报错但很慢」的接口。

中间件刻意用**原生 ASGI** 写，而不是 ``BaseHTTPMiddleware``：后者会把响应体
包进一层管道，配合 SSE（AI 客服的流式输出）会破坏实时性。这里只在
``http.response.start`` 上补一个响应头，完全不碰 body。

同一个中间件顺手把耗时喂给 Prometheus 指标（见 ``app/core/metrics.py``）：
**计时只做一次，两个消费者**——重复包中间件既浪费也不容易保证两边口径一致。
"""

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.datastructures import Headers, MutableHeaders

from app.core.config import settings
from app.core.metrics import observe as observe_metrics

access_logger = logging.getLogger("app.access")

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id.get()


def bind_request_id(request_id: str):
    """把 request_id 绑到当前上下文，返回用于还原的 token。"""
    return _request_id.set(request_id)


def reset_request_id(token) -> None:
    _request_id.reset(token)


class _RequestIdFilter(logging.Filter):
    """给每条日志补上 request_id，这样 JSON 日志里永远有这个字段。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        for key in ("method", "path", "status", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    """配置根 logger。LOG_JSON=true 时输出单行 JSON（便于日志系统采集）。"""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestIdFilter())
    if settings.log_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
            )
        )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # 我们自己会记录带耗时与 request_id 的访问日志，关掉 uvicorn 的默认版本避免重复
    logging.getLogger("uvicorn.access").disabled = True


class RequestContextMiddleware:
    """原生 ASGI 中间件：注入 request_id、记录访问日志、回写响应头。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = Headers(scope=scope).get("x-request-id") or uuid.uuid4().hex[:16]
        token = bind_request_id(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message).append("X-Request-ID", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            observe_metrics(
                scope.get("method", "UNKNOWN"), scope, status_code, duration_ms / 1000
            )
            extra = {
                "method": scope.get("method"),
                "path": scope.get("path"),
                "status": status_code,
                "duration_ms": round(duration_ms, 1),
            }
            if duration_ms >= settings.log_slow_request_ms:
                access_logger.warning("慢请求", extra=extra)
            else:
                access_logger.info("请求完成", extra=extra)
            reset_request_id(token)
