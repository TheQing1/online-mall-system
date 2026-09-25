"""后台任务：订单超时自动关单等。"""

import asyncio
import logging

from app.core.database import SessionLocal
from app.services import order_service

logger = logging.getLogger(__name__)


async def _cancel_expired_orders_loop(interval_seconds: int = 30):
    while True:
        try:
            await asyncio.to_thread(_cancel_expired_orders_once)
        except Exception:
            logger.exception("订单超时检查失败")
        await asyncio.sleep(interval_seconds)


def _cancel_expired_orders_once():
    db = SessionLocal()
    try:
        count = order_service.auto_cancel_expired_orders(db)
        if count:
            logger.info("自动取消超时订单 %s 笔", count)
    finally:
        db.close()


async def start_background_tasks(app):
    """由 FastAPI lifespan 调用，应用关闭时停止。"""
    app.state.background_task = asyncio.create_task(_cancel_expired_orders_loop())
    yield
    app.state.background_task.cancel()
