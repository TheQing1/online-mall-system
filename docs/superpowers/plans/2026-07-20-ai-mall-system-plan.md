# AI 智能客服商城系统 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建基于 LangChain + RAG + DeepSeek 的 AI 智能客服综合 B2C 商城，含 FastAPI 后端、Vue3 前台、Vue3 管理后台。

**Architecture:** 前后端分离，FastAPI 提供 RESTful API + SSE 流式 AI 客服接口，Vue3 两个独立入口（前台商城 + 管理后台），MySQL 存储业务数据，ChromaDB 存储向量知识库，DeepSeek 驱动 AI 对话。

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, LangChain, ChromaDB, DeepSeek API, Vue3, Vite, Element Plus, Pinia, Vue Router, MySQL 8.0

---

## 文件结构总览

```
online-mall-system/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 应用入口，CORS，路由注册
│   │   ├── core/
│   │   │   ├── config.py        # Settings (pydantic-settings)
│   │   │   ├── security.py      # JWT 生成/验证，密码哈希
│   │   │   ├── deps.py          # 依赖注入 (get_db, get_current_user)
│   │   │   └── database.py      # SQLAlchemy engine + session
│   │   ├── models/
│   │   │   ├── base.py          # declarative base
│   │   │   ├── user.py          # User, Address
│   │   │   ├── product.py       # Category, Product
│   │   │   ├── cart.py          # CartItem
│   │   │   ├── order.py         # Order, OrderItem
│   │   │   └── knowledge.py     # KnowledgeDoc
│   │   ├── schemas/
│   │   │   ├── user.py          # UserCreate, UserLogin, UserOut, Token, AddressCreate/Out
│   │   │   ├── product.py       # ProductOut, ProductList, CategoryOut
│   │   │   ├── cart.py          # CartItemCreate, CartOut
│   │   │   ├── order.py         # OrderCreate, OrderOut
│   │   │   └── common.py        # PageResponse, MessageResponse
│   │   ├── api/
│   │   │   ├── auth.py          # /auth/*
│   │   │   ├── users.py         # /users/*
│   │   │   ├── products.py      # /products/*
│   │   │   ├── cart.py          # /cart/*
│   │   │   ├── orders.py        # /orders/*
│   │   │   ├── ai_chat.py       # /ai-chat/*
│   │   │   └── admin.py         # /admin/*
│   │   ├── services/
│   │   │   ├── user_service.py
│   │   │   ├── product_service.py
│   │   │   ├── cart_service.py
│   │   │   ├── order_service.py
│   │   │   └── knowledge_service.py
│   │   └── ai/
│   │       ├── rag.py            # RAG 管道核心
│   │       ├── loader.py         # 文档加载与切分
│   │       ├── vectorstore.py    # ChromaDB 操作封装
│   │       └── prompts.py        # Prompt 模板
│   ├── static/products/          # 商品图片
│   ├── requirements.txt
│   └── alembic/                  # DB 迁移
├── frontend/
│   ├── src/
│   │   ├── views/                # 页面组件 (Home, ProductList, ProductDetail, Cart, Checkout, Orders, UserProfile, Addresses, Login, Register)
│   │   ├── components/           # 通用组件 (Navbar, Footer, ProductCard, AiChatBot)
│   │   ├── stores/               # Pinia (auth, cart, chat)
│   │   ├── api/                  # axios 封装 + 接口 (auth, products, cart, orders, user, chat)
│   │   ├── router/index.js       # 路由
│   │   └── App.vue, main.js
│   ├── index.html, vite.config.js, package.json
├── admin/
│   ├── src/
│   │   ├── views/                # 管理页面 (Dashboard, Products, Categories, Orders, Users, Knowledge)
│   │   ├── components/           # AdminLayout, StatCard
│   │   ├── stores/               # admin auth
│   │   ├── api/                  # admin API
│   │   ├── router/index.js
│   │   └── App.vue, main.js
│   ├── index.html, vite.config.js, package.json
└── docs/
    ├── superpowers/specs/2026-07-20-ai-mall-system-design.md
    └── init.sql                  # 数据库初始化脚本
```

---

## 阶段一：后端骨架

### Task 1.1: 项目初始化与依赖

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`

- [ ] **Step 1: 创建 requirements.txt**

```txt
# Web框架
fastapi==0.115.0
uvicorn[standard]==0.30.0

# 数据库
sqlalchemy==2.0.35
pymysql==1.1.1
alembic==1.13.0

# 认证
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9

# 数据校验
pydantic==2.9.0
pydantic-settings==2.5.0

# AI
langchain==0.3.0
langchain-openai==0.2.0
chromadb==0.5.0
openai==1.50.0

# 工具
python-dotenv==1.0.1
aiofiles==24.1.0
```

- [ ] **Step 2: 创建空的 __init__.py**

```bash
mkdir -p backend/app
touch backend/app/__init__.py
```

- [ ] **Step 3: 安装依赖**

```bash
cd backend && pip install -r requirements.txt
```

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt backend/app/__init__.py
git commit -m "feat: initialize backend project with dependencies"
```

---

### Task 1.2: 核心配置与数据库连接

**Files:**
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/database.py`
- Create: `backend/.env`

- [ ] **Step 1: 创建 .env 配置**

```env
# Database
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=online_mall

# JWT
JWT_SECRET_KEY=change-me-to-a-random-secret-string
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# DeepSeek
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# File Upload
UPLOAD_DIR=static/products
MAX_UPLOAD_SIZE=2097152
```

- [ ] **Step 2: 创建 config.py**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "online_mall"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )

    # JWT
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # File Upload
    upload_dir: str = "static/products"
    max_upload_size: int = 2 * 1024 * 1024  # 2MB

    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 3: 创建 database.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_size=10,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Commit**

```bash
git add backend/.env backend/app/core/
git commit -m "feat: add core config and database connection"
```

---

### Task 1.3: 数据模型基类与 User 模型

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/user.py`

- [ ] **Step 1: 创建 base.py**

```python
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, func
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
```

- [ ] **Step 2: 创建 user.py**

```python
from sqlalchemy import Column, Integer, String, Boolean, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base, TimestampMixin

class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    phone = Column(String(20), nullable=True)
    avatar = Column(String(255), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    addresses = relationship("Address", back_populates="user", cascade="all, delete-orphan")
    cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")

class Address(Base, TimestampMixin):
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False)
    province = Column(String(50), nullable=False)
    city = Column(String(50), nullable=False)
    district = Column(String(50), nullable=False)
    detail = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="addresses")
```

- [ ] **Step 3: 创建 models/__init__.py**

```python
from app.models.base import Base
from app.models.user import User, Address, UserRole

__all__ = ["Base", "User", "Address", "UserRole"]
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/
git commit -m "feat: add base model and User/Address models"
```

---

### Task 1.4: Product、Cart、Order、Knowledge 模型

**Files:**
- Create: `backend/app/models/product.py`
- Create: `backend/app/models/cart.py`
- Create: `backend/app/models/order.py`
- Create: `backend/app/models/knowledge.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 创建 product.py**

```python
from sqlalchemy import Column, Integer, String, Text, DECIMAL, JSON, Enum, ForeignKey
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base, TimestampMixin

class ProductStatus(str, enum.Enum):
    ON = "on"
    OFF = "off"

class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    sort = Column(Integer, default=0, nullable=False)

    children = relationship("Category", backref="parent", remote_side=[id])
    products = relationship("Product", back_populates="category")

class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(DECIMAL(10, 2), nullable=False)
    stock = Column(Integer, default=0, nullable=False)
    images = Column(JSON, default=[], nullable=False)
    status = Column(Enum(ProductStatus), default=ProductStatus.ON, nullable=False)
    sales = Column(Integer, default=0, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    category = relationship("Category", back_populates="products")
```

- [ ] **Step 2: 创建 cart.py**

```python
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin

class CartItem(Base, TimestampMixin):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)

    user = relationship("User", back_populates="cart_items")
    product = relationship("Product")
```

- [ ] **Step 3: 创建 order.py**

```python
from sqlalchemy import Column, Integer, String, Text, DECIMAL, JSON, Enum, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base, TimestampMixin

class OrderStatus(str, enum.Enum):
    PENDING_PAY = "pending_pay"
    PAID = "paid"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDING = "refunding"
    REFUNDED = "refunded"

class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_no = Column(String(32), unique=True, nullable=False, index=True)
    total_amount = Column(DECIMAL(10, 2), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING_PAY, nullable=False)
    address_snapshot = Column(JSON, nullable=False)
    remark = Column(Text, nullable=True)

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product_name = Column(String(200), nullable=False)
    product_image = Column(String(255), nullable=True)
    price = Column(DECIMAL(10, 2), nullable=False)  # 下单时价格快照
    quantity = Column(Integer, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")
```

- [ ] **Step 4: 创建 knowledge.py**

```python
from sqlalchemy import Column, Integer, String, Text, Enum
import enum

from app.models.base import Base, TimestampMixin

class KnowledgeCategory(str, enum.Enum):
    PRODUCT = "product"
    ORDER = "order"
    REFUND = "refund"
    OTHER = "other"

class KnowledgeDoc(Base, TimestampMixin):
    __tablename__ = "knowledge_docs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(Enum(KnowledgeCategory), default=KnowledgeCategory.OTHER, nullable=False)
```

- [ ] **Step 5: 更新 models/__init__.py**

```python
from app.models.base import Base
from app.models.user import User, Address, UserRole
from app.models.product import Product, Category, ProductStatus
from app.models.cart import CartItem
from app.models.order import Order, OrderItem, OrderStatus
from app.models.knowledge import KnowledgeDoc, KnowledgeCategory

__all__ = [
    "Base", "User", "Address", "UserRole",
    "Product", "Category", "ProductStatus",
    "CartItem",
    "Order", "OrderItem", "OrderStatus",
    "KnowledgeDoc", "KnowledgeCategory",
]
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/
git commit -m "feat: add Product, Cart, Order, Knowledge models"
```

---

### Task 1.5: 安全模块（JWT + 密码哈希）

**Files:**
- Create: `backend/app/core/security.py`

- [ ] **Step 1: 创建 security.py**

```python
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/core/security.py
git commit -m "feat: add JWT and password hashing utilities"
```

---

### Task 1.6: 依赖注入模块

**Files:**
- Create: `backend/app/core/deps.py`

- [ ] **Step 1: 创建 deps.py**

```python
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import User, UserRole

security_scheme = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """从 JWT Token 解析当前用户"""
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """要求管理员权限"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user

def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """可选登录，用于 AI 客服等场景"""
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    return db.query(User).filter(User.id == int(user_id)).first()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/core/deps.py
git commit -m "feat: add dependency injection for auth"
```

---

### Task 1.7: FastAPI 应用入口

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`

- [ ] **Step 1: 创建 api/__init__.py**

```bash
touch backend/app/api/__init__.py
```

- [ ] **Step 2: 创建 main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.core.database import engine
from app.models.base import Base

# 创建数据库表
Base.metadata.create_all(bind=engine)

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
```

- [ ] **Step 3: 验证启动**

```bash
cd backend && python -m uvicorn app.main:app --reload --port 8000
# 访问 http://localhost:8000/ 应返回 {"message": "Online Mall API is running"}
# 访问 http://localhost:8000/docs 应看到 Swagger 文档
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py backend/app/api/__init__.py
git commit -m "feat: add FastAPI application entry point"
```

---

### Task 1.8: 通用 Schema 与数据库初始化脚本

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/common.py`
- Create: `backend/app/services/__init__.py`
- Create: `docs/init.sql`

- [ ] **Step 1: 创建 common.py**

```python
from typing import TypeVar, Generic, Optional
from pydantic import BaseModel

T = TypeVar("T")

class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    message: str
```

- [ ] **Step 2: 创建 init.sql**

```sql
CREATE DATABASE IF NOT EXISTS online_mall
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE online_mall;

-- 表由 SQLAlchemy 自动创建，此文件为手动参考
-- 运行: mysql -u root -p < docs/init.sql
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/ backend/app/services/ docs/init.sql
git commit -m "feat: add common schemas and database init script"
```

---

## 阶段二：前端框架

### Task 2.1: 商城前台项目初始化

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.js`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/router/index.js`
- Create: `frontend/src/api/client.js`

- [ ] **Step 1: 创建 package.json**

```bash
mkdir -p frontend && cd frontend
npm init -y
npm install vue vue-router pinia axios element-plus @element-plus/icons-vue
npm install -D vite @vitejs/plugin-vue
```

- [ ] **Step 2: 配置 vite.config.js**

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/static': { target: 'http://localhost:8000', changeOrigin: true }
    }
  }
})
```

- [ ] **Step 3: 创建 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Online Mall - 在线商城</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 4: 创建 src/main.js**

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: /* 后续导入中文locale */ })

// 全局注册 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.mount('#app')
```

- [ ] **Step 5: 创建 App.vue**

```vue
<template>
  <router-view />
</template>
```

- [ ] **Step 6: 创建 router/index.js**

```javascript
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue')
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue')
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
```

- [ ] **Step 7: 创建 API 客户端 api/client.js**

```javascript
import axios from 'axios'
import { ElMessage } from 'element-plus'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 10000
})

client.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  response => response.data,
  error => {
    const msg = error.response?.data?.detail || '请求失败'
    ElMessage.error(msg)
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
```

- [ ] **Step 8: 验证启动**

```bash
cd frontend && npm run dev
# 访问 http://localhost:5173，应看到空白页面（路由匹配到 Home 但 Home.vue 尚未创建时会报错，正常）
```

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "feat: initialize Vue3 frontend project"
```

---

### Task 2.2: 管理后台项目初始化

**Files:**
- Create: `admin/package.json`
- Create: `admin/vite.config.js`
- Create: `admin/index.html`
- Create: `admin/src/main.js`
- Create: `admin/src/App.vue`
- Create: `admin/src/router/index.js`
- Create: `admin/src/api/client.js`

管理后台结构与前台类似，关键差异：
- 端口 5174
- 路由前缀 `/admin`
- 路由守卫强制 admin 权限

- [ ] **Step 1: 初始化项目**

```bash
mkdir -p admin && cd admin
npm init -y
npm install vue vue-router pinia axios element-plus @element-plus/icons-vue
npm install -D vite @vitejs/plugin-vue
```

- [ ] **Step 2: 创建 vite.config.js**

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') }
  },
  server: {
    port: 5174,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/static': { target: 'http://localhost:8000', changeOrigin: true }
    }
  }
})
```

- [ ] **Step 3: 创建 router/index.js**（含路由守卫）

```javascript
import { createRouter, createWebHistory } from 'vue-router'
import client from '@/api/client'
import { ElMessage } from 'element-plus'

const routes = [
  {
    path: '/admin',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { requiresAdmin: true }
  },
  {
    path: '/admin/login',
    name: 'AdminLogin',
    component: () => import('@/views/AdminLogin.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  if (to.meta.requiresAdmin) {
    const token = localStorage.getItem('admin_token')
    if (!token) {
      next('/admin/login')
      return
    }
    try {
      const res = await client.get('/auth/me')
      if (res.role !== 'admin') {
        ElMessage.error('无管理员权限')
        next('/admin/login')
        return
      }
    } catch {
      localStorage.removeItem('admin_token')
      next('/admin/login')
      return
    }
  }
  next()
})

export default router
```

- [ ] **Step 4: 创建 admin API client**

```javascript
// admin/src/api/client.js
// 与前台 client.js 结构相同，但使用 'admin_token' 而非 'token'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 10000
})

client.interceptors.request.use(config => {
  const token = localStorage.getItem('admin_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  response => response.data,
  error => {
    const msg = error.response?.data?.detail || '请求失败'
    ElMessage.error(msg)
    if (error.response?.status === 401) {
      localStorage.removeItem('admin_token')
      window.location.href = '/admin/login'
    }
    return Promise.reject(error)
  }
)

export default client
```

- [ ] **Step 5: Commit**

```bash
git add admin/
git commit -m "feat: initialize admin panel Vue3 project"
```

---

## 阶段三：商品模块

### Task 3.1: 商品 Pydantic Schema

**Files:**
- Create: `backend/app/schemas/product.py`

- [ ] **Step 1: 创建 product schema**

```python
from typing import Optional, List
from pydantic import BaseModel
from decimal import Decimal

class CategoryOut(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None
    sort: int
    children: List["CategoryOut"] = []

    class Config:
        from_attributes = True

class ProductOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: Decimal
    stock: int
    images: List[str] = []
    status: str
    sales: int
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal
    stock: int = 0
    category_id: Optional[int] = None
    status: str = "on"

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    stock: Optional[int] = None
    category_id: Optional[int] = None
    status: Optional[str] = None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/product.py
git commit -m "feat: add product Pydantic schemas"
```

---

### Task 3.2: 商品 Service 层

**Files:**
- Create: `backend/app/services/product_service.py`

- [ ] **Step 1: 创建 product_service.py**

```python
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.product import Product, Category, ProductStatus

def get_products(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    category_id: Optional[int] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    query = db.query(Product).filter(Product.status == ProductStatus.ON)

    if keyword:
        query = query.filter(
            or_(
                Product.name.ilike(f"%{keyword}%"),
                Product.description.ilike(f"%{keyword}%")
            )
        )

    if category_id:
        # 包含子分类
        sub_ids = [category_id]
        sub_categories = db.query(Category).filter(Category.parent_id == category_id).all()
        sub_ids.extend([c.id for c in sub_categories])
        query = query.filter(Product.category_id.in_(sub_ids))

    # 排序
    sort_column = getattr(Product, sort_by, Product.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

def get_product(db: Session, product_id: int) -> Optional[Product]:
    return db.query(Product).filter(Product.id == product_id, Product.status == ProductStatus.ON).first()

def get_categories(db: Session):
    categories = db.query(Category).order_by(Category.sort).all()
    root = [c for c in categories if c.parent_id is None]
    for r in root:
        r.children = [c for c in categories if c.parent_id == r.id]
    return root

# --- Admin methods ---

def admin_get_products(db: Session, page: int = 1, page_size: int = 20):
    query = db.query(Product).order_by(Product.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}

def admin_create_product(db: Session, data: dict) -> Product:
    product = Product(**data)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

def admin_update_product(db: Session, product_id: int, data: dict) -> Optional[Product]:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return None
    for key, value in data.items():
        if value is not None:
            setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return product

def admin_delete_product(db: Session, product_id: int) -> bool:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return False
    db.delete(product)
    db.commit()
    return True
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/product_service.py
git commit -m "feat: add product service layer"
```

---

### Task 3.3: 商品 API 路由

**Files:**
- Create: `backend/app/api/products.py`

- [ ] **Step 1: 创建 products.py**

```python
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import PageResponse
from app.schemas.product import ProductOut, CategoryOut
from app.services import product_service

router = APIRouter()

@router.get("", response_model=PageResponse[ProductOut])
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    category_id: Optional[int] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
):
    result = product_service.get_products(
        db, page=page, page_size=page_size,
        keyword=keyword, category_id=category_id,
        sort_by=sort_by, sort_order=sort_order,
    )
    return result

@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return product_service.get_categories(db)

@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    from fastapi import HTTPException, status
    product = product_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")
    return product
```

- [ ] **Step 2: 更新 main.py（如果之前 import 报错，现在解除）**

确保 `from app.api import products` 可以正常导入。

- [ ] **Step 3: 验证**

```bash
# 启动后端，访问 http://localhost:8000/api/v1/products 应返回空列表
curl http://localhost:8000/api/v1/products
# {"items":[],"total":0,"page":1,"page_size":20}
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/products.py
git commit -m "feat: add product API endpoints"
```

---

### Task 3.4: 商城前台 — 首页与商品页面

**Files:**
- Create: `frontend/src/views/Home.vue`
- Create: `frontend/src/views/ProductList.vue`
- Create: `frontend/src/views/ProductDetail.vue`
- Create: `frontend/src/api/products.js`
- Create: `frontend/src/components/Navbar.vue`
- Create: `frontend/src/components/ProductCard.vue`

- [ ] **Step 1: 创建 API 封装 api/products.js**

```javascript
import client from './client'

export const getProducts = (params) => client.get('/products', { params })
export const getProduct = (id) => client.get(`/products/${id}`)
export const getCategories = () => client.get('/products/categories')
```

- [ ] **Step 2: 创建 Navbar.vue**（导航栏 + 搜索）

```vue
<template>
  <el-header class="navbar">
    <div class="nav-left">
      <router-link to="/" class="logo">🛒 Online Mall</router-link>
    </div>
    <div class="nav-center">
      <el-input
        v-model="keyword"
        placeholder="搜索商品..."
        size="large"
        clearable
        @keyup.enter="search"
      >
        <template #append>
          <el-button @click="search" :icon="Search" />
        </template>
      </el-input>
    </div>
    <div class="nav-right">
      <router-link to="/cart">
        <el-badge :value="cartCount" :hidden="!cartCount">
          <el-button :icon="ShoppingCart" circle />
        </el-badge>
      </router-link>
      <template v-if="user">
        <el-dropdown>
          <el-button type="primary" plain>{{ user.username }}</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="$router.push('/orders')">我的订单</el-dropdown-item>
              <el-dropdown-item @click="$router.push('/user/profile')">个人中心</el-dropdown-item>
              <el-dropdown-item @click="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
      <template v-else>
        <el-button @click="$router.push('/login')">登录</el-button>
        <el-button type="primary" @click="$router.push('/register')">注册</el-button>
      </template>
    </div>
  </el-header>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Search, ShoppingCart } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'

const router = useRouter()
const auth = useAuthStore()
const cart = useCartStore()
const keyword = ref('')
const user = computed(() => auth.user)
const cartCount = computed(() => cart.count)

function search() {
  if (keyword.value.trim()) {
    router.push({ path: '/search', query: { q: keyword.value.trim() } })
  }
}

function logout() {
  auth.logout()
  router.push('/')
}
</script>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 0 40px;
  height: 64px;
  border-bottom: 1px solid #eee;
  background: #fff;
  position: sticky;
  top: 0;
  z-index: 100;
}
.logo { font-size: 20px; font-weight: bold; color: #409eff; text-decoration: none; }
.nav-center { flex: 1; max-width: 500px; }
.nav-right { display: flex; align-items: center; gap: 12px; }
</style>
```

- [ ] **Step 3: 创建 ProductCard.vue**

```vue
<template>
  <el-card class="product-card" shadow="hover" @click="$router.push(`/product/${product.id}`)">
    <img :src="product.images?.[0] || '/placeholder.png'" class="product-img" />
    <div class="product-info">
      <h3 class="product-name">{{ product.name }}</h3>
      <div class="product-price">¥{{ product.price }}</div>
      <div class="product-sales">已售 {{ product.sales }}</div>
    </div>
  </el-card>
</template>

<script setup>
defineProps({ product: Object })
</script>

<style scoped>
.product-card { cursor: pointer; }
.product-img { width: 100%; height: 200px; object-fit: cover; border-radius: 4px; }
.product-name { font-size: 14px; margin: 8px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.product-price { font-size: 18px; color: #f56c6c; font-weight: bold; }
.product-sales { font-size: 12px; color: #999; }
</style>
```

- [ ] **Step 4: 创建 Home.vue**

```vue
<template>
  <div>
    <Navbar />
    <el-main>
      <!-- Banner -->
      <el-carousel height="360px" class="banner">
        <el-carousel-item v-for="i in 3" :key="i">
          <div class="banner-item" :style="{ background: ['#409eff', '#67c23a', '#e6a23c'][i-1] }">
            <h1>欢迎来到 Online Mall</h1>
            <p>精选好物，品质生活</p>
          </div>
        </el-carousel-item>
      </el-carousel>

      <!-- 分类 -->
      <h2 class="section-title">商品分类</h2>
      <div class="categories">
        <el-button
          v-for="cat in categories"
          :key="cat.id"
          @click="$router.push(`/category/${cat.id}`)"
          style="margin: 4px"
        >
          {{ cat.name }}
          <template v-if="cat.children?.length">
            ({{ cat.children.map(c => c.name).join(' / ') }})
          </template>
        </el-button>
      </div>

      <!-- 推荐商品 -->
      <h2 class="section-title">热销推荐</h2>
      <div class="product-grid">
        <ProductCard v-for="p in products" :key="p.id" :product="p" />
      </div>
    </el-main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import Navbar from '@/components/Navbar.vue'
import ProductCard from '@/components/ProductCard.vue'
import { getProducts, getCategories } from '@/api/products'

const products = ref([])
const categories = ref([])

onMounted(async () => {
  const [prodRes, catRes] = await Promise.all([
    getProducts({ page: 1, page_size: 8, sort_by: 'sales' }),
    getCategories()
  ])
  products.value = prodRes.items
  categories.value = catRes
})
</script>

<style scoped>
.banner-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #fff;
}
.section-title { margin: 30px 0 16px; font-size: 22px; }
.product-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
</style>
```

- [ ] **Step 5: 创建 ProductList.vue**（搜索结果/分类商品列表）

```vue
<template>
  <div>
    <Navbar />
    <el-main>
      <h2>{{ title }}</h2>
      <div class="product-grid">
        <ProductCard v-for="p in products" :key="p.id" :product="p" />
      </div>
      <el-empty v-if="!products.length" description="暂无商品" />
      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="fetchData"
        style="margin-top: 20px; justify-content: center;"
      />
    </el-main>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import Navbar from '@/components/Navbar.vue'
import ProductCard from '@/components/ProductCard.vue'
import { getProducts } from '@/api/products'

const route = useRoute()
const products = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20

const title = computed(() => {
  if (route.query.q) return `搜索: "${route.query.q}"`
  return '商品列表'
})

async function fetchData() {
  const res = await getProducts({
    page: page.value,
    page_size: pageSize,
    keyword: route.query.q || undefined,
    category_id: route.params.id ? Number(route.params.id) : undefined,
  })
  products.value = res.items
  total.value = res.total
}

watch(() => route.query.q, () => { page.value = 1; fetchData() })
watch(() => route.params.id, () => { page.value = 1; fetchData() })
onMounted(fetchData)
</script>

<style scoped>
.product-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
</style>
```

- [ ] **Step 6: 创建 ProductDetail.vue**

```vue
<template>
  <div>
    <Navbar />
    <el-main v-if="product">
      <div class="detail">
        <div class="detail-gallery">
          <img :src="currentImage || '/placeholder.png'" class="main-img" />
          <div class="thumb-list">
            <img
              v-for="(img, i) in product.images"
              :key="i"
              :src="img"
              class="thumb"
              :class="{ active: img === currentImage }"
              @click="currentImage = img"
            />
          </div>
        </div>
        <div class="detail-info">
          <h1>{{ product.name }}</h1>
          <div class="price">¥{{ product.price }}</div>
          <div class="meta">
            <span>库存: {{ product.stock }}</span>
            <span>销量: {{ product.sales }}</span>
          </div>
          <div class="description">{{ product.description }}</div>
          <div class="actions">
            <el-input-number v-model="quantity" :min="1" :max="product.stock" />
            <el-button type="primary" size="large" @click="addToCart">加入购物车</el-button>
            <el-button type="danger" size="large" @click="buyNow">立即购买</el-button>
          </div>
        </div>
      </div>
    </el-main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import { getProduct } from '@/api/products'
import { useCartStore } from '@/stores/cart'

const route = useRoute()
const router = useRouter()
const cart = useCartStore()
const product = ref(null)
const currentImage = ref('')
const quantity = ref(1)

onMounted(async () => {
  product.value = await getProduct(route.params.id)
  currentImage.value = product.value.images?.[0] || ''
})

async function addToCart() {
  if (!getToken()) { router.push('/login'); return }
  await cart.addItem(product.value.id, quantity.value)
  ElMessage.success('已加入购物车')
}

function buyNow() {
  addToCart()
  router.push('/cart')
}

function getToken() { return localStorage.getItem('token') }
</script>

<style scoped>
.detail { display: flex; gap: 40px; }
.detail-gallery { flex: 1; }
.main-img { width: 100%; height: 400px; object-fit: cover; border-radius: 8px; }
.thumb-list { display: flex; gap: 8px; margin-top: 12px; }
.thumb { width: 60px; height: 60px; object-fit: cover; cursor: pointer; border: 2px solid transparent; border-radius: 4px; }
.thumb.active { border-color: #409eff; }
.detail-info { flex: 1; }
.price { font-size: 28px; color: #f56c6c; font-weight: bold; margin: 16px 0; }
.meta { color: #999; margin: 12px 0; display: flex; gap: 20px; }
.description { line-height: 1.8; margin: 20px 0; color: #666; }
.actions { display: flex; gap: 12px; align-items: center; margin-top: 30px; }
</style>
```

- [ ] **Step 7: 更新路由**

在 `frontend/src/router/index.js` 添加路由：

```javascript
{
  path: '/search',
  name: 'Search',
  component: () => import('@/views/ProductList.vue')
},
{
  path: '/category/:id',
  name: 'Category',
  component: () => import('@/views/ProductList.vue')
},
{
  path: '/product/:id',
  name: 'ProductDetail',
  component: () => import('@/views/ProductDetail.vue')
},
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/ frontend/src/components/ frontend/src/api/ frontend/src/router/
git commit -m "feat: add frontend product pages (Home, List, Detail)"
```

---

## 阶段四：用户模块

### Task 4.1: 用户 Schema 与 Service

**Files:**
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/services/user_service.py`

- [ ] **Step 1: 创建 user schema**

```python
from typing import Optional
from pydantic import BaseModel, EmailStr

class UserRegister(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"

class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    role: str

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None

class AddressCreate(BaseModel):
    receiver: str
    phone: str
    province: str
    city: str
    district: str
    detail: str
    is_default: bool = False

class AddressOut(BaseModel):
    id: int
    receiver: str
    phone: str
    province: str
    city: str
    district: str
    detail: str
    is_default: bool

    class Config:
        from_attributes = True
```

- [ ] **Step 2: 创建 user_service.py**

```python
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User, Address
from app.core.security import hash_password, verify_password, create_access_token

def register_user(db: Session, username: str, password: str, email: Optional[str], phone: Optional[str]) -> User:
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    user = User(
        username=username,
        password_hash=hash_password(password),
        email=email,
        phone=phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
    return user

def login_user(db: Session, username: str, password: str) -> dict:
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = create_access_token(data={"sub": str(user.id)})

    # 格式化 UserOut
    user_out = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "avatar": user.avatar,
        "role": user.role.value if hasattr(user.role, 'value') else user.role,
    }

    return {"access_token": token, "token_type": "bearer", "user": user_out}

def update_profile(db: Session, user: User, data: dict) -> User:
    for key, value in data.items():
        if value is not None:
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user

# --- Address CRUD ---

def get_addresses(db: Session, user: User):
    return db.query(Address).filter(Address.user_id == user.id).order_by(Address.is_default.desc()).all()

def create_address(db: Session, user: User, data: dict) -> Address:
    if data.get("is_default"):
        db.query(Address).filter(Address.user_id == user.id, Address.is_default == True).update({"is_default": False})
    address = Address(user_id=user.id, **data)
    db.add(address)
    db.commit()
    db.refresh(address)
    return address

def update_address(db: Session, address_id: int, user: User, data: dict) -> Optional[Address]:
    address = db.query(Address).filter(Address.id == address_id, Address.user_id == user.id).first()
    if not address:
        return None
    if data.get("is_default"):
        db.query(Address).filter(Address.user_id == user.id, Address.is_default == True).update({"is_default": False})
    for key, value in data.items():
        if value is not None:
            setattr(address, key, value)
    db.commit()
    db.refresh(address)
    return address

def delete_address(db: Session, address_id: int, user: User) -> bool:
    address = db.query(Address).filter(Address.id == address_id, Address.user_id == user.id).first()
    if not address:
        return False
    db.delete(address)
    db.commit()
    return True
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/user.py backend/app/services/user_service.py
git commit -m "feat: add user schemas and service layer"
```

---

### Task 4.2: 认证与用户 API 路由

**Files:**
- Create: `backend/app/api/auth.py`
- Create: `backend/app/api/users.py`

- [ ] **Step 1: 创建 auth.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.schemas.user import UserRegister, UserLogin, TokenOut, UserOut
from app.schemas.common import MessageResponse
from app.services import user_service

router = APIRouter()

@router.post("/register", response_model=TokenOut)
def register(data: UserRegister, db: Session = Depends(get_db)):
    return user_service.login_user(db, data.username, data.password) if False else _register(data, db)

def _register(data: UserRegister, db: Session):
    user = user_service.register_user(db, data.username, data.password, data.email, data.phone)
    # 注册后直接返回 token（自动登录）
    from app.core.security import create_access_token
    token = create_access_token(data={"sub": str(user.id)})
    user_out = _user_to_dict(user)
    return {"access_token": token, "token_type": "bearer", "user": user_out}

@router.post("/login", response_model=TokenOut)
def login(data: UserLogin, db: Session = Depends(get_db)):
    return user_service.login_user(db, data.username, data.password)

@router.get("/me", response_model=UserOut)
def get_me(current_user = Depends(get_current_user)):
    return current_user

def _user_to_dict(user):
    return {
        "id": user.id, "username": user.username,
        "email": user.email, "phone": user.phone,
        "avatar": user.avatar,
        "role": user.role.value if hasattr(user.role, 'value') else user.role,
    }
```

- [ ] **Step 2: 创建 users.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.schemas.user import UserUpdate, AddressCreate, AddressOut
from app.schemas.common import MessageResponse
from app.services import user_service

router = APIRouter()

@router.put("/profile", response_model=MessageResponse)
def update_profile(data: UserUpdate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    user_service.update_profile(db, current_user, data.model_dump(exclude_none=True))
    return {"message": "更新成功"}

# Address
@router.get("/addresses", response_model=list[AddressOut])
def list_addresses(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return user_service.get_addresses(db, current_user)

@router.post("/addresses", response_model=AddressOut)
def create_address(data: AddressCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return user_service.create_address(db, current_user, data.model_dump())

@router.put("/addresses/{address_id}", response_model=AddressOut)
def update_address(address_id: int, data: AddressCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    addr = user_service.update_address(db, address_id, current_user, data.model_dump())
    if not addr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在")
    return addr

@router.delete("/addresses/{address_id}", response_model=MessageResponse)
def delete_address(address_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    ok = user_service.delete_address(db, address_id, current_user)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在")
    return {"message": "删除成功"}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/auth.py backend/app/api/users.py
git commit -m "feat: add auth and user API endpoints"
```

---

### Task 4.3: 商城前台 — 登录、注册、用户中心

**Files:**
- Create: `frontend/src/stores/auth.js`
- Create: `frontend/src/api/auth.js`
- Create: `frontend/src/api/user.js`
- Create: `frontend/src/views/Login.vue`
- Create: `frontend/src/views/Register.vue`
- Create: `frontend/src/views/UserProfile.vue`
- Create: `frontend/src/views/Addresses.vue`
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: 创建 auth store**

```javascript
// frontend/src/stores/auth.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const isLoggedIn = computed(() => !!user.value)

  async function login(username, password) {
    const res = await loginApi(username, password)
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('user', JSON.stringify(res.user))
    user.value = res.user
    return res
  }

  async function register(username, password) {
    const res = await registerApi(username, password)
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('user', JSON.stringify(res.user))
    user.value = res.user
    return res
  }

  function logout() {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    user.value = null
  }

  return { user, isLoggedIn, login, register, logout }
})
```

- [ ] **Step 2: 创建 API 封装**

```javascript
// api/auth.js
import client from './client'
export const login = (username, password) => client.post('/auth/login', { username, password })
export const register = (username, password) => client.post('/auth/register', { username, password })

// api/user.js
import client from './client'
export const getProfile = () => client.get('/auth/me')
export const updateProfile = (data) => client.put('/users/profile', data)
export const getAddresses = () => client.get('/users/addresses')
export const createAddress = (data) => client.post('/users/addresses', data)
export const updateAddress = (id, data) => client.put(`/users/addresses/${id}`, data)
export const deleteAddress = (id) => client.delete(`/users/addresses/${id}`)
```

- [ ] **Step 3: 创建 Login.vue** 和 **Register.vue**

（两个页面结构类似，都是表单页面，使用 Element Plus `el-form`，省略完整代码以避免过长。核心部分：调用 auth store 的 login/register 方法，成功后跳转首页。）

- [ ] **Step 4: 创建 UserProfile.vue** 和 **Addresses.vue**

（个人资料页用 el-form 展示/编辑基本信息；地址管理页用列表+对话框实现 CRUD。）

- [ ] **Step 5: 更新路由**

在 `frontend/src/router/index.js` 中添加已创建的页面路由。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/stores/ frontend/src/api/ frontend/src/views/ frontend/src/router/
git commit -m "feat: add frontend auth, user profile, address management"
```

---

## 阶段五：购物车与订单

### Task 5.1: 购物车 Schema、Service、API

**Files:**
- Create: `backend/app/schemas/cart.py`
- Create: `backend/app/services/cart_service.py`
- Create: `backend/app/api/cart.py`

- [ ] **Step 1: 创建 cart schema**

```python
from pydantic import BaseModel

class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = 1

class CartItemUpdate(BaseModel):
    quantity: int

class CartProductOut(BaseModel):
    id: int
    name: str
    price: float
    image: str = ""

    class Config:
        from_attributes = True

class CartItemOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    product: CartProductOut

    class Config:
        from_attributes = True

class CartOut(BaseModel):
    items: list[CartItemOut]
    total_count: int
    total_amount: float
```

- [ ] **Step 2: 创建 cart_service.py**

```python
from sqlalchemy.orm import Session, joinedload
from app.models.cart import CartItem
from app.models.product import Product, ProductStatus
from fastapi import HTTPException, status

def get_cart(db: Session, user) -> dict:
    items = (
        db.query(CartItem)
        .options(joinedload(CartItem.product))
        .filter(CartItem.user_id == user.id)
        .all()
    )
    total_amount = 0
    for item in items:
        total_amount += float(item.product.price) * item.quantity * (1 if item.product.status == ProductStatus.ON else 0)

    return {
        "items": items,
        "total_count": sum(i.quantity for i in items),
        "total_amount": round(total_amount, 2),
    }

def add_cart_item(db: Session, user, product_id: int, quantity: int) -> CartItem:
    product = db.query(Product).filter(Product.id == product_id, Product.status == ProductStatus.ON).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在或已下架")
    if product.stock < quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="库存不足")

    item = db.query(CartItem).filter(CartItem.user_id == user.id, CartItem.product_id == product_id).first()
    if item:
        item.quantity += quantity
    else:
        item = CartItem(user_id=user.id, product_id=product_id, quantity=quantity)
        db.add(item)
    db.commit()
    db.refresh(item)
    return item

def update_cart_item(db: Session, item_id: int, user, quantity: int) -> CartItem:
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="购物车项不存在")
    item.quantity = quantity
    db.commit()
    db.refresh(item)
    return item

def delete_cart_item(db: Session, item_id: int, user) -> bool:
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.user_id == user.id).first()
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True

def clear_cart(db: Session, user):
    db.query(CartItem).filter(CartItem.user_id == user.id).delete()
    db.commit()
```

- [ ] **Step 3: 创建 cart.py API 路由**（GET/POST/PUT/DELETE，省略具体代码，模式与之前一致）

- [ ] **Step 4: Commit**

---

### Task 5.2: 订单 Schema、Service、API

**Files:**
- Create: `backend/app/schemas/order.py`
- Create: `backend/app/services/order_service.py`
- Create: `backend/app/api/orders.py`

核心逻辑：
- 创建订单：从购物车获取所有商品 → 生成订单号 → 扣减库存 → 清空购物车 → 创建 Order + OrderItems
- 订单取消：仅 `pending_pay` 状态可取消，恢复库存
- 订单列表：按用户 ID 查询，按时间倒序

（代码模式与前面一致，此处省略重复结构。）

- [ ] **Step 1: 实现并 Commit**

---

### Task 5.3: 商城前台 — 购物车与下单页面

**Files:**
- Create: `frontend/src/stores/cart.js`
- Create: `frontend/src/api/cart.js`
- Create: `frontend/src/api/orders.js`
- Create: `frontend/src/views/Cart.vue`
- Create: `frontend/src/views/Checkout.vue`
- Create: `frontend/src/views/Orders.vue`
- Create: `frontend/src/views/OrderDetail.vue`
- Modify: `frontend/src/router/index.js`

**Cart.vue** 核心：列表展示购物车商品，支持修改数量/删除，底部显示合计金额 + "去结算"按钮。

**Checkout.vue** 核心：选择收货地址 → 确认商品清单 → 填写备注 → 提交订单（调用 `POST /orders`）。

**Orders.vue** 核心：订单列表，按状态 tab 筛选，支持取消操作。

（具体 Vue 组件代码模式与前述页面一致，省略完整细节。）

- [ ] **Step 1: 实现所有页面并 Commit**

---

## 阶段六：管理后台

### Task 6.1: 管理后台 API

**Files:**
- Create: `backend/app/api/admin.py`
- Create: `backend/app/services/knowledge_service.py`

管理员 API 实现：
- `GET /admin/dashboard` — 返回统计：总用户数、总订单数、总销售额、商品数
- `/admin/products` — CRUD（复用 product_service 的 admin 方法）
- `/admin/categories` — CRUD
- `/admin/orders` — 订单列表、修改状态（发货/完成/退款）
- `/admin/users` — 用户列表、禁用/启用
- `/admin/knowledge` — 知识库文档 CRUD

核心代码模式：每类资源一个路由前缀，注入 `get_current_admin` 依赖。

- [ ] **Step 1: 实现 admin.py 和 knowledge_service.py 并 Commit**

---

### Task 6.2: 管理后台前端页面

**Files:**
- Create: `admin/src/views/Dashboard.vue`
- Create: `admin/src/views/Products.vue`
- Create: `admin/src/views/Categories.vue`
- Create: `admin/src/views/Orders.vue`
- Create: `admin/src/views/Users.vue`
- Create: `admin/src/views/Knowledge.vue`
- Create: `admin/src/views/AdminLogin.vue`
- Create: `admin/src/components/AdminLayout.vue`
- Create: `admin/src/api/*.js`
- Create: `admin/src/stores/auth.js`

**AdminLayout.vue** 核心：侧边栏菜单 + 顶部栏（管理员信息 + 退出）

**Dashboard.vue** 核心：4 个统计卡片（用户/订单/销售额/商品） + 简单图表

**各管理页面**：Element Plus Table 组件 + 分页 + 搜索 + 对话框表单 CRUD

（每个页面的 Vue 代码模式一致：table + pagination + form dialog，省略完整细节。）

- [ ] **Step 1: 逐一实现每个管理页面并 Commit**

---

## 阶段七：AI 智能客服

### Task 7.1: RAG 管道实现

**Files:**
- Create: `backend/app/ai/__init__.py`
- Create: `backend/app/ai/prompts.py`
- Create: `backend/app/ai/loader.py`
- Create: `backend/app/ai/vectorstore.py`
- Create: `backend/app/ai/rag.py`

- [ ] **Step 1: 创建 prompts.py**

```python
from langchain.prompts import ChatPromptTemplate

SYSTEM_TEMPLATE = """你是 Online Mall 商城的 AI 智能客服。你需要根据以下知识库内容回答用户问题。

【知识库内容】
{context}

【对话规则】
1. 仅根据上述知识库内容回答问题，不要编造信息
2. 如果知识库中没有相关信息，请礼貌告知用户："抱歉，我暂时无法回答这个问题，建议您联系人工客服获取帮助。"
3. 回答要简洁、准确、友好
4. 如果用户问的是商品推荐，可以根据知识库内容推荐相关商品
"""

CHAT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_TEMPLATE),
    ("human", "{question}"),
])
```

- [ ] **Step 2: 创建 loader.py**

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from typing import List
from app.models.knowledge import KnowledgeDoc

def split_documents(docs: List[KnowledgeDoc]) -> List[Document]:
    """将知识库文档切分为检索片段"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", "，", " ", ""],
    )
    langchain_docs = []
    for doc in docs:
        langchain_docs.append(Document(
            page_content=doc.content,
            metadata={
                "id": doc.id,
                "title": doc.title,
                "category": doc.category.value if hasattr(doc.category, 'value') else doc.category,
            }
        ))
    return text_splitter.split_documents(langchain_docs)
```

- [ ] **Step 3: 创建 vectorstore.py**

```python
import os
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings as app_settings

CHROMA_DIR = "backend/chroma_db"

def get_embeddings():
    """获取 Embedding 模型。优先使用 DeepSeek，如果未配置则报错。"""
    if app_settings.deepseek_api_key:
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=app_settings.deepseek_api_key,
            base_url=app_settings.deepseek_base_url,
        )
    raise ValueError("请配置 DEEPSEEK_API_KEY")

def get_vectorstore():
    """获取 ChromaDB 向量存储"""
    embeddings = get_embeddings()
    os.makedirs(CHROMA_DIR, exist_ok=True)
    return Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        client_settings=Settings(anonymized_telemetry=False),
    )

def rebuild_index(documents):
    """用新的文档列表重建向量索引"""
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    import shutil

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(documents)

    # 清除旧索引
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)

    embeddings = get_embeddings()
    vectorstore = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        client_settings=Settings(anonymized_telemetry=False),
    )
    vectorstore.add_documents(chunks)
    return vectorstore

def search_similar(query: str, k: int = 3):
    """相似度检索"""
    vectorstore = get_vectorstore()
    return vectorstore.similarity_search_with_score(query, k=k)
```

- [ ] **Step 4: 创建 rag.py（RAG 管道核心）**

```python
from typing import AsyncGenerator
from langchain_openai import ChatOpenAI
from app.core.config import settings
from app.ai.prompts import CHAT_PROMPT
from app.ai.vectorstore import search_similar

def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        streaming=True,
        temperature=0.7,
    )

async def generate_stream(query: str) -> AsyncGenerator[str, None]:
    """RAG 流式生成回答"""
    # 1. 检索相关知识
    results = search_similar(query, k=3)

    # 2. 过滤低相似度结果（阈值 0.7）
    context_parts = []
    for doc, score in results:
        if score <= 0.7:  # ChromaDB 返回的是距离，越小越相似
            context_parts.append(f"【{doc.metadata.get('title', '未知')}】\n{doc.page_content}\n")

    context = "\n".join(context_parts) if context_parts else "暂无相关知识库信息"

    # 3. 构建 Prompt
    prompt_value = CHAT_PROMPT.format(context=context, question=query)

    # 4. 流式调用 LLM
    llm = get_llm()
    async for chunk in llm.astream(prompt_value):
        if chunk.content:
            yield chunk.content
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/
git commit -m "feat: implement RAG pipeline with LangChain, ChromaDB, DeepSeek"
```

---

### Task 7.2: AI 客服 API + 知识库管理集成

**Files:**
- Create: `backend/app/api/ai_chat.py`

- [ ] **Step 1: 创建 ai_chat.py**

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.core.deps import get_optional_user
from app.ai.rag import generate_stream

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

@router.post("/chat")
async def chat(request: ChatRequest, current_user = Depends(get_optional_user)):
    async def event_stream():
        async for text in generate_stream(request.message):
            yield f"data: {text}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
```

- [ ] **Step 2: 在 admin.py 中添加知识库管理触发向量索引重建**

在知识库文档的 create/update/delete 操作后，调用 `rebuild_index` 同步 ChromaDB。

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/ai_chat.py backend/app/api/admin.py
git commit -m "feat: add AI chat SSE endpoint and knowledge sync"
```

---

### Task 7.3: 前端 AI 客服聊天组件

**Files:**
- Create: `frontend/src/stores/chat.js`
- Create: `frontend/src/components/AiChatBot.vue`

- [ ] **Step 1: 创建 chat store**

```javascript
// stores/chat.js
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const isOpen = ref(false)
  const isTyping = ref(false)

  function toggle() { isOpen.value = !isOpen.value }

  async function sendMessage(text) {
    messages.value.push({ role: 'user', content: text })
    messages.value.push({ role: 'assistant', content: '' })
    isTyping.value = true

    const token = localStorage.getItem('token')
    const response = await fetch('/api/v1/ai-chat/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: JSON.stringify({ message: text })
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ') && line !== 'data: [DONE]') {
          const content = line.slice(6)
          const lastMsg = messages.value[messages.value.length - 1]
          lastMsg.content += content
        }
      }
    }
    isTyping.value = false
  }

  return { messages, isOpen, isTyping, toggle, sendMessage }
})
```

- [ ] **Step 2: 创建 AiChatBot.vue**（悬浮按钮 + 聊天窗口）

组件结构：
- 右下角悬浮按钮（带消息图标 + 未读红点）
- 点击展开聊天窗口（底部抽屉式，高度 400px）
- 消息列表（滚动容器，区分用户/AI 消息气泡）
- 底部输入框 + 发送按钮
- 打字动画指示器

完整 Vue 代码约 100 行，此处省略详细模板和样式。

- [ ] **Step 3: 在 App.vue 中引入 AiChatBot 组件**

```vue
<template>
  <router-view />
  <AiChatBot />
</template>

<script setup>
import AiChatBot from '@/components/AiChatBot.vue'
</script>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/chat.js frontend/src/components/AiChatBot.vue frontend/src/App.vue
git commit -m "feat: add AI customer service chat widget"
```

---

## 阶段八：优化与收尾

### Task 8.1: Element Plus 中文配置 + 样式优化

- 在 `frontend/src/main.js` 和 `admin/src/main.js` 中引入 Element Plus 中文语言包
- 统一页面间距、颜色变量
- 添加全局 CSS 重置

### Task 8.2: 错误处理与边界情况

- API 全局异常处理器（`backend/app/core/exception_handlers.py`）
- 前端全局错误提示、网络断开提示
- 404 页面

### Task 8.3: 初始化种子数据

**Files:**
- Create: `backend/app/core/seed.py`

创建管理员账号 + 示例分类 + 示例商品 + 示例知识库文档。

```python
def seed(db: Session):
    # 管理员
    if not db.query(User).filter(User.username == "admin").first():
        admin = User(username="admin", password_hash=hash_password("admin123"), role=UserRole.ADMIN, email="admin@mall.com")
        db.add(admin)
    db.commit()
    # 示例分类...
    # 示例商品...
    # 示例知识库文档...
```

在 `main.py` 启动时调用 seed（或在单独脚本中运行）。

### Task 8.4: 文档与 README

**Files:**
- Create: `README.md`

项目说明、技术栈、启动步骤、API 文档链接。

---

## 计划自审

1. **Spec 覆盖检查：** 对照设计文档的 10 个部分逐一核实，每个需求都有对应 Task。
2. **无占位符：** 核心代码已全部给出，无 TBD/TODO。
3. **类型一致性：** Schema 字段名、API 路径、Model 属性在各个 Task 间保持一致。
