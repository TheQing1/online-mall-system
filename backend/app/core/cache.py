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
import random
import threading
import time
from typing import Any, Callable, Dict, Optional

import redis

from app.core.config import settings
from app.core.metrics import cache_operations_total, redis_up

logger = logging.getLogger(__name__)

_client: Optional["redis.Redis"] = None
_client_lock = threading.Lock()
_unavailable_until = 0.0
_RETRY_AFTER_SECONDS = 30.0

# 负缓存的占位值：存进 Redis 的是一段 JSON，所以用一个普通字符串当哨兵
NEGATIVE_CACHE = "__cache_miss__"

# 单飞用的「按 key 的进程内锁」
_key_locks: Dict[str, threading.Lock] = {}
_key_locks_guard = threading.Lock()


def jittered_ttl(ttl: int, ratio: float = 0.1) -> int:
    """给 TTL 加 ±ratio 的随机抖动，最小 1 秒。

    解决**缓存雪崩**：如果一批 key 是同一时刻写入的（比如服务重启后第一次
    批量预热），它们会在同一秒集体过期，请求会在那一瞬间全压到数据库上。
    抖动把过期时间打散，代价只是缓存命中率略微下降。
    """
    delta = max(1, int(ttl * ratio))
    return max(1, ttl + random.randint(-delta, delta))


def _key_lock(key: str) -> threading.Lock:
    with _key_locks_guard:
        lock = _key_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _key_locks[key] = lock
        return lock


def cache_get_or_load(
    key: str,
    ttl: int,
    loader: Callable[[], Any],
    *,
    negative_ttl: int = 30,
) -> Any:
    """未命中时加载并写回；同一 key 的并发未命中只会真正查一次数据源。

    三层保护分别对应三个经典问题：

    - **缓存击穿**：热点 key 过期的一瞬间，N 个请求同时未命中、同时查库。
      用「按 key 的进程内锁」做单飞：只有一个请求去加载，其余等它填好缓存后直接读。
    - **缓存穿透**：查一个根本不存在的 id（或恶意构造的 id）时，每次都绕过缓存打到库里。
      ``loader`` 返回 None 就写一条很短的**负缓存**兜住。
    - **缓存雪崩**：见 ``jittered_ttl``，调用方传进来的 TTL 建议先过一遍它。

    诚实说明边界：单飞是**进程内**的，多副本部署时每个副本仍可能各查一次
    （要彻底解决得用分布式锁 + 短等待）。本项目单实例部署够用，
    Redis 不可用时这里退化为「每次都查库」，也就是回到没有缓存的样子——
    不会更差，但也不会更好。
    """
    cached = cache_get(key)
    if cached is not None:
        return None if cached == NEGATIVE_CACHE else cached

    with _key_lock(key):
        # 双检：等锁期间可能已经有别的线程把缓存填好了
        cached = cache_get(key)
        if cached is not None:
            return None if cached == NEGATIVE_CACHE else cached

        value = loader()
        if value is None:
            cache_set(key, NEGATIVE_CACHE, negative_ttl)
            cache_operations_total.labels(result="negative").inc()
        else:
            cache_set(key, value, ttl)
        return value


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
            redis_up.set(0)
            logger.warning("Redis 不可用，降级为无缓存/不限流：%s", exc)
            return None
        _client = client
        redis_up.set(1)
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
        cache_operations_total.labels(result="error").inc()
        logger.warning("读缓存失败（按未命中处理）：%s", exc)
        return None
    if raw is None:
        cache_operations_total.labels(result="miss").inc()
        return None
    try:
        cache_operations_total.labels(result="hit").inc()
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
        cache_operations_total.labels(result="set").inc()
    except Exception as exc:
        cache_operations_total.labels(result="error").inc()
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
