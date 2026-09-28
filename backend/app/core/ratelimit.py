"""接口限流：固定窗口计数（Redis INCR + EXPIRE）。

为什么用固定窗口而不是滑动窗口/令牌桶：实现只有两条命令，够用，缺点是窗口
边界可能出现两倍突发（第 59 秒和第 61 秒各打满一次）。本项目不是秒杀场景，
这个精度足够；要更平滑就换令牌桶。

为什么 key 优先用用户而不是 IP：同一出口 IP（公司、校园网、运营商 NAT）后面
可能有很多正常用户，按 IP 限流会误伤；登录接口则只能用 IP，因为那时还没有用户。

Redis 不可用时**放行**（fail-open）：限流是防滥用的，不该因为它自己挂掉就把
正常用户挡在门外。代价是那段时间没有保护——这是明确的取舍。
"""

import logging
from typing import Optional

from fastapi import HTTPException, Request, status

from app.core.cache import get_redis
from app.core.config import settings
from app.core.metrics import rate_limit_blocked_total
from app.core.security import decode_access_token

logger = logging.getLogger(__name__)

# 各接口的默认配额都从 settings 现读（而不是在装饰时求值），
# 这样测试和压测可以直接改配置，不用去动已经注册好的依赖。
_LIMIT_SETTINGS = {
    "api": "rate_limit_api",
    "login": "rate_limit_login",
    "order": "rate_limit_order",
    "chat": "rate_limit_chat",
}


def _resolve_limit(scope: str, explicit: Optional[int]) -> Optional[int]:
    if explicit is not None:
        return explicit
    setting_name = _LIMIT_SETTINGS.get(scope)
    return getattr(settings, setting_name) if setting_name else None


def client_identity(request: Request) -> str:
    """已登录按用户限流，未登录按来源 IP。

    这里直接读 ``request.client.host`` 而不是自己解析 X-Forwarded-For：
    uvicorn 已经用 ``--proxy-headers`` 把它还原成真实客户端 IP 了，
    自己再解析一遍反而会把伪造 XFF 的口子重新打开。
    """
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        payload = decode_access_token(header[7:])
        if payload and payload.get("sub"):
            return f"user:{payload['sub']}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def rate_limit(scope: str, limit: Optional[int] = None, window: Optional[int] = None):
    """构造一个限流依赖：``Depends(rate_limit("login"))``。

    ``limit`` 缺省时按 ``scope`` 去 settings 里取（见 ``_LIMIT_SETTINGS``）；
    配额配成 0 或负数表示**关闭**该限流——压测时用得着。
    """

    async def dependency(request: Request) -> None:
        quota = _resolve_limit(scope, limit)
        if not quota or quota <= 0:
            return

        client = get_redis()
        if client is None:
            return  # fail-open，见模块文档

        seconds = window or settings.rate_limit_window_seconds
        key = f"rl:{scope}:{client_identity(request)}"
        try:
            pipe = client.pipeline()
            pipe.incr(key)
            pipe.ttl(key)
            count, ttl = pipe.execute()
            if ttl is not None and ttl < 0:
                # 第一次计数时补上过期时间；ttl < 0 表示 key 没有 TTL
                client.expire(key, seconds)
                ttl = seconds
        except Exception as exc:
            logger.warning("限流检查失败，本次放行：%s", exc)
            return

        if count > quota:
            retry_after = max(int(ttl), 1)
            rate_limit_blocked_total.labels(scope=scope).inc()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"操作过于频繁，请 {retry_after} 秒后再试",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
