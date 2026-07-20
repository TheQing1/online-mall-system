from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.core.database import engine
from app.models.base import Base

# 创建数据库表（开发环境容错处理）
try:
    Base.metadata.create_all(bind=engine)
except Exception:
    pass

app = FastAPI(title="Online Mall API", version="1.0.0")

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
from app.api import auth, products, users, cart, orders, ai_chat, admin

app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(products.router, prefix="/api/v1/products", tags=["商品"])
app.include_router(users.router, prefix="/api/v1/users", tags=["用户"])
app.include_router(cart.router, prefix="/api/v1/cart", tags=["购物车"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["订单"])
app.include_router(ai_chat.router, prefix="/api/v1/ai-chat", tags=["AI客服"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["管理后台"])


@app.get("/")
def root():
    return {"message": "Online Mall API is running"}
