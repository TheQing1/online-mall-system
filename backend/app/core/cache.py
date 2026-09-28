"""Redis 客户端与缓存封装。

缓存、限流、分布式锁共用同一个客户端，因为它们必须遵守同一条原则：
**Redis 挂了，业务不能跟着挂**。

- 连接带 200ms 超时：Redis 不可达时宁可降级，也不能把请求线程拖死；
- 连接失败后 30 秒内不再重试（简易熔断），避免每个请求都白等一次超时；
- 降级时只打一条 warning：缓存读返回未命中、写静默丢弃、限流直接放行。

代价说清楚：降级期间没有缓存也没有限流保护，是拿「可用性」换「保护强度」。
对商城这类读多写少的业务，可用性优先是对的。
"""

import json
import logging
import threading
import time
from typing import Any, Optional

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Optional["redis.Redis"] = None
_client_lock = threading.Lock()
_unavailable_until = 0.0
_RETRY_AFTER_SECONDS = 30.0


def get_redis() -> Optional["redis.Redis"]:
    """返回可用的 Redis 客户端；不可用时返回 None，调用方按降级处理。"""
    global _client, _unavailable_until
    if _client is not None:
        return _client
    if time.monotonic() < _unavailable_until:
        return None

    with _client_lock:
        if _client is not None:
            return _client
        if time.monotonic() < _unavailable_until:
            return None
        try:
            client = redis.Redis.from_url(
                settings.redis_url,
                socket_connect_timeout=settings.redis_connect_timeout,
                socket_timeout=settings.redis_connect_timeout,
                decode_responses=True,
            )
            client.ping()
        except Exception as exc:
            _unavailable_until = time.monotonic() + _RETRY_AFTER_SECONDS
            logger.warning("Redis 不可用，降级为无缓存/不限流：%s", exc)
            return None
        _client = client
        logger.info("Redis 已连接：%s", settings.redis_url)
        return _client


def reset_client() -> None:
    """丢掉客户端与熔断状态（配置变更、测试用）。"""
    global _client, _unavailable_until
    _client = None
    _unavailable_until = 0.0


def cache_get(key: str) -> Optional[Any]:
    client = get_redis()
    if client is None:
        return None
    try:
        raw = client.get(key)
    except Exception as exc:
        logger.warning("读缓存失败（按未命中处理）：%s", exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("缓存内容不是合法 JSON，已忽略：%s", key)
        return None


def cache_set(key: str, value: Any, ttl: int) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        client.set(key, json.dumps(value, ensure_ascii=False, default=str), ex=ttl)
    except Exception as exc:
        logger.warning("写缓存失败（忽略）：%s", exc)


def cache_delete(*keys: str) -> None:
    client = get_redis()
    if client is None or not keys:
        return
    try:
        client.delete(*keys)
    except Exception as exc:
        logger.warning("删除缓存失败（忽略）：%s", exc)


def cache_delete_prefix(prefix: str) -> int:
    """按前缀批量删除，返回删除条数。

    用 SCAN 而不是 KEYS：KEYS 会阻塞整个 Redis（命令复杂度 O(N)），
    在生产上是事故级别的操作；SCAN 是游标式的，每次只返回一小批。
    """
    client = get_redis()
    if client is None:
        return 0
    removed = 0
    try:
        for key in client.scan_iter(match=f"{prefix}*", count=200):
            client.delete(key)
            removed += 1
    except Exception as exc:
        logger.warning("按前缀清理缓存失败（忽略）：%s", exc)
    return removed
