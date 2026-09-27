from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings, startup_problems
from app.core.tasks import start_background_tasks

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
    async for _ in start_background_tasks(app):
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

app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(products.router, prefix="/api/v1/products", tags=["商品"])
app.include_router(banners.router, prefix="/api/v1/banners", tags=["运营"])
app.include_router(users.router, prefix="/api/v1/users", tags=["用户"])
app.include_router(cart.router, prefix="/api/v1/cart", tags=["购物车"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["订单"])
app.include_router(ai_chat.router, prefix="/api/v1/ai-chat", tags=["AI客服"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["管理后台"])


@app.get("/")
def root():
    return {"message": "Online Mall API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}
