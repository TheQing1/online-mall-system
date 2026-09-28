"""后台任务：订单超时自动关单。

两种跑法，由 ``RUN_BACKGROUND_TASKS`` 决定：

- true（开发默认）：挂在 FastAPI 的 lifespan 上，跟着 API 进程一起跑；
- false（多副本部署）：由独立进程跑 ``python -m app.core.tasks``，
  见 docker-compose 里的 worker 服务。

不管哪种跑法，每一轮都先用 Redis 分布式锁串行化，避免 N 个副本重复扫表。
Redis 不可用时退化成各跑各的——任务本身幂等（条件 UPDATE 抢状态），所以安全。
"""

import asyncio
import logging

from app.core.database import SessionLocal
from app.core.locks import redis_lock
from app.core.logging_config import setup_logging
from app.core.metrics import background_task_runs_total
from app.services import order_service

logger = logging.getLogger(__name__)

_LOCK_NAME = "cancel_expired_orders"
_TASK_NAME = "cancel_expired_orders"


async def _cancel_expired_orders_loop(interval_seconds: int = 30):
    while True:
        try:
            await asyncio.to_thread(_cancel_expired_orders_once)
        except Exception:
            background_task_runs_total.labels(task=_TASK_NAME, result="error").inc()
            logger.exception("订单超时检查失败")
        await asyncio.sleep(interval_seconds)


def _cancel_expired_orders_once() -> int:
    """跑一轮超时关单，返回取消笔数。"""
    # 锁的租约要大于单轮耗时，又不能太长：60 秒 = 两个执行周期，
    # 万一进程被杀，最多 60 秒后其他副本就能接手。
    with redis_lock(_LOCK_NAME, ttl_seconds=60) as handle:
        if not handle.acquired:
            logger.debug("另一个副本正在执行关单，本轮跳过")
            background_task_runs_total.labels(task=_TASK_NAME, result="skipped").inc()
            return 0
        if handle.degraded:
            logger.debug("Redis 不可用，本轮无锁执行（任务幂等）")

        db = SessionLocal()
        try:
            count = order_service.auto_cancel_expired_orders(db)
            background_task_runs_total.labels(task=_TASK_NAME, result="ok").inc()
            if count:
                logger.info("自动取消超时订单 %s 笔", count)
            return count
        finally:
            db.close()


async def start_background_tasks(app):
    """由 FastAPI lifespan 调用，应用关闭时停止。"""
    app.state.background_task = asyncio.create_task(_cancel_expired_orders_loop())
    yield
    app.state.background_task.cancel()


def main() -> None:
    """独立 worker 入口：``python -m app.core.tasks``"""
    setup_logging()
    logger.info("定时任务 worker 启动：订单超时关单，每 30 秒一轮")
    try:
        asyncio.run(_cancel_expired_orders_loop())
    except KeyboardInterrupt:  # pragma: no cover - 手工停止
        logger.info("worker 收到中断信号，退出")


if __name__ == "__main__":  # pragma: no cover
    main()
