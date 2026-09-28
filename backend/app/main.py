from contextlib import asynccontextmanager
import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings, startup_problems
from app.core.logging_config import RequestContextMiddleware, setup_logging
from app.core.metrics import metrics_response
from app.core.ratelimit import rate_limit
from app.core.tasks import start_background_tasks

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    problems = startup_problems(settings)
    if problems:
        # 生产环境直接拒绝启动；开发环境只告警，保证 clone 下来就能跑。
        if settings.environment.lower() in {"production", "prod"}:
            raise RuntimeError("配置自检未通过：" + "；".join(problems))
        for problem in problems:
            logger.warning("配置自检：%s", problem)
    if settings.run_background_tasks:
        async for _ in start_background_tasks(app):
            yield
    else:
        logger.info(
            "RUN_BACKGROUND_TASKS=false：本进程不启动定时任务（由独立 worker 负责）"
        )
        yield


app = FastAPI(title="Online Mall API", version="2.0.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 放在 CORS 之后添加 => 位于中间件栈最外层，能覆盖包括 CORS 预检在内的所有响应
app.add_middleware(RequestContextMiddleware)

# 静态文件（商品图片）
os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 注册路由（后续逐步添加）
from app.api import (
    auth,
    products,
    banners,
    users,
    cart,
    orders,
    ai_chat,
    admin,
)

# 全站兜底限流：所有业务接口都按「用户 / 来源 IP」限一个总配额，
# 个别接口再叠加更严的配额（登录 10/分、下单 20/分、AI 对话 20/分）。
# 配额配成 0 可以关掉，压测时用得上。
api_guard = [Depends(rate_limit("api"))]

app.include_router(
    auth.router, prefix="/api/v1/auth", tags=["认证"], dependencies=api_guard
)
app.include_router(
    products.router, prefix="/api/v1/products", tags=["商品"], dependencies=api_guard
)
app.include_router(
    banners.router, prefix="/api/v1/banners", tags=["运营"], dependencies=api_guard
)
app.include_router(
    users.router, prefix="/api/v1/users", tags=["用户"], dependencies=api_guard
)
app.include_router(
    cart.router, prefix="/api/v1/cart", tags=["购物车"], dependencies=api_guard
)
app.include_router(
    orders.router, prefix="/api/v1/orders", tags=["订单"], dependencies=api_guard
)
app.include_router(
    ai_chat.router, prefix="/api/v1/ai-chat", tags=["AI客服"], dependencies=api_guard
)
app.include_router(
    admin.router, prefix="/api/v1/admin", tags=["管理后台"], dependencies=api_guard
)


@app.get("/")
def root():
    return {"message": "Online Mall API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
def metrics():
    """Prometheus 指标。只挂在后端端口上：nginx 只反代 /api、/static、/health，
    所以它不会随站点对外暴露（生产上也应该只让监控系统访问）。
    """
    return metrics_response()
