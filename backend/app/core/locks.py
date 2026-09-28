"""基于 Redis 的分布式锁。

目前只有一个使用场景：订单超时自动关单。

先说清楚它**不是**为了修正确性：关单本身已经是幂等的（用
``UPDATE ... WHERE status = 'pending_pay'`` 抢，只有抢到的那个调用会回补库存，
见 ``order_service.auto_cancel_expired_orders``）。加锁是为了另外两件事：

1. 多副本部署时，N 个副本每 30 秒各扫一遍同一张 ``orders`` 表纯属浪费，
   还会互相抢行锁；
2. 让「定时任务」在多副本下真的有唯一实例，而不是「靠幂等兜着」。

用 redis-py 自带的 ``Lock`` 而不是手写 ``SET NX``：它的释放已经是
「校验 token 再删除」的原子实现（内部用 Lua），不会误删别人持有的锁。
拿不到锁时返回 None，调用方直接跳过这一轮即可。
"""

import logging
from contextlib import contextmanager
from typing import Iterator, NamedTuple

from app.core.cache import get_redis

logger = logging.getLogger(__name__)


class LockHandle(NamedTuple):
    """``acquired``：本次是否拿到锁；``degraded``：是否因为 Redis 不可用退化成无锁。"""

    acquired: bool
    degraded: bool = False


@contextmanager
def redis_lock(name: str, ttl_seconds: int = 60) -> Iterator[LockHandle]:
    """尝试获取名为 ``name`` 的锁；不阻塞、不排队，结果见 ``LockHandle``。

    ``blocking=False`` 是有意的：定时任务这一轮抢不到就跳过，
    等 30 秒后的下一轮，而不是排队把线程占住。
    """
    client = get_redis()
    if client is None:
        # Redis 不可用时退化为「每个副本各跑一遍」——任务本身幂等，不会出错
        yield LockHandle(acquired=True, degraded=True)
        return

    lock = client.lock(f"lock:{name}", timeout=ttl_seconds, blocking=False)
    acquired = False
    try:
        acquired = bool(lock.acquire())
    except Exception as exc:
        logger.warning("获取分布式锁失败，本轮按未持锁处理：%s", exc)
    if not acquired:
        yield LockHandle(acquired=False)
        return

    try:
        yield LockHandle(acquired=True)
    finally:
        try:
            lock.release()
        except Exception as exc:  # pragma: no cover - 只在锁超时后才可能发生
            logger.warning("释放分布式锁失败（锁可能已超时）：%s", exc)
