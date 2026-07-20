# 基于 LangChain 的 AI 智能客服商城系统 — 设计文档

> 创建日期: 2026-07-20
> 状态: 已确认

## 1. 项目概述

构建一个综合 B2C 在线商城系统，集成基于 LangChain + RAG 的 AI 智能客服，为用户提供商品浏览、购买及智能问答服务。

## 2. 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue3 + Element Plus + Vite | 商城前台 + 管理后台，两个独立入口 |
| 后端 | FastAPI + SQLAlchemy + Pydantic | RESTful API，JWT 认证 |
| 数据库 | MySQL 8.0 | 用户、商品、订单等核心业务数据 |
| 向量库 | ChromaDB | 轻量级，Python 原生，存储知识库文档向量 |
| AI 框架 | LangChain | 文档加载 → 切片 → Embedding → 检索 → 生成 |
| 大模型 | DeepSeek (`deepseek-chat`) | API 兼容 OpenAI 格式，中文能力强 |
| Embedding | DeepSeek Embedding 或 `bge-large-zh` | 中文语义检索 |
| 存储 | 本地文件系统 | 商品图片上传 |
| 支付 | 模拟支付 | 下单后直接标记支付成功 |

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      前端层 (Vue3)                        │
│  ┌──────────────────┐  ┌──────────────────────────────┐  │
│  │   商城前台 (Web)   │  │     管理后台 (Admin)          │  │
│  │  Element Plus     │  │     Element Plus             │  │
│  │  • 商品浏览/搜索    │  │     • 商品/分类管理           │  │
│  │  • 购物车/下单     │  │     • 订单处理               │  │
│  │  • 用户中心        │  │     • 用户管理               │  │
│  │  • AI客服悬浮窗    │  │     • 数据统计               │  │
│  └────────┬─────────┘  └─────────────┬────────────────┘  │
└───────────┼──────────────────────────┼────────────────────┘
            │          HTTP/REST + SSE  │
            ▼                           ▼
┌─────────────────────────────────────────────────────────┐
│                    后端 API 层 (FastAPI)                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│  │ 商品 API  │ │ 用户 API  │ │ 订单 API  │ │ AI 客服 API │ │
│  └─────┬────┘ └────┬─────┘ └────┬─────┘ └──────┬─────┘ │
│        └───────────┴────────────┴──────────────┘         │
└──────────────────────────┼────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌─────────┐ ┌──────────┐ ┌───────────┐
        │  MySQL  │ │ ChromaDB │ │ 文件存储   │
        │ (业务数据)│ │ (向量知识库)│ │ (商品图片) │
        └─────────┘ └──────────┘ └───────────┘
                           │
                           ▼
              ┌──────────────────────┐
              │   DeepSeek API       │
              └──────────────────────┘
```

## 4. 核心数据模型

### 实体关系

| 实体 | 核心字段 | 说明 |
|------|---------|------|
| User | id, username, password(hash), email, phone, avatar, role(user/admin) | role 区分普通用户和管理员 |
| Address | id, user_id, receiver, phone, province/city/district/detail, is_default | 收货地址 |
| Category | id, name, parent_id(nullable), sort | 支持两级分类 |
| Product | id, name, description, price, stock, images(JSON数组), status(on/off), sales, category_id | 商品 |
| CartItem | id, user_id, product_id, quantity | 购物车项 |
| Order | id, user_id, order_no, total_amount, status, address_snapshot(JSON), remark | 订单 |
| OrderItem | id, order_id, product_id, price(snapshot), quantity | 订单明细 |
| KnowledgeDoc | id, title, content, category(产品/订单/退换货/其他), created_at | RAG 知识库 |

### 订单状态流转

```
pending_pay → paid → shipped → completed
     │          │
     └── cancelled
                │
                └── refunding → refunded
```

## 5. API 设计概览

### 基础路径: `/api/v1`

| 模块 | 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|------|
| 认证 | `/auth/register` | POST | 注册 | - |
| 认证 | `/auth/login` | POST | 登录，返回 JWT | - |
| 认证 | `/auth/me` | GET | 当前用户信息 | JWT |
| 用户 | `/users/profile` | PUT | 修改资料 | JWT |
| 用户 | `/users/addresses` | GET/POST | 地址列表/新增 | JWT |
| 用户 | `/users/addresses/{id}` | PUT/DEL | 修改/删除地址 | JWT |
| 商品 | `/products` | GET | 商品列表(分页/搜索/筛选) | - |
| 商品 | `/products/{id}` | GET | 商品详情 | - |
| 商品 | `/products/categories` | GET | 分类树 | - |
| 购物车 | `/cart` | GET | 查看购物车 | JWT |
| 购物车 | `/cart/items` | POST | 添加到购物车 | JWT |
| 购物车 | `/cart/items/{id}` | PUT/DEL | 修改数量/删除 | JWT |
| 订单 | `/orders` | POST | 创建订单 | JWT |
| 订单 | `/orders` | GET | 我的订单列表 | JWT |
| 订单 | `/orders/{id}` | GET | 订单详情 | JWT |
| 订单 | `/orders/{id}/cancel` | PUT | 取消订单 | JWT |
| AI客服 | `/ai-chat/chat` | POST | 发送消息(SSE流式返回) | 可选 |
| 管理 | `/admin/dashboard` | GET | 数据统计 | Admin |
| 管理 | `/admin/products` | CRUD | 商品管理 | Admin |
| 管理 | `/admin/categories` | CRUD | 分类管理 | Admin |
| 管理 | `/admin/orders` | GET/PUT | 订单管理 | Admin |
| 管理 | `/admin/users` | GET/PUT | 用户管理 | Admin |
| 管理 | `/admin/knowledge` | CRUD | 知识库管理 | Admin |

### AI 客服通信方式

使用 **SSE (Server-Sent Events)** 而非 WebSocket：
- 交互模式为"用户发一条 → AI 流式返回"，单向流即可满足
- FastAPI `StreamingResponse` 原生支持，无需额外依赖
- 浏览器内置自动重连，实现简单

## 6. 前端页面路由

### 商城前台 (`/`)

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 首页 | Banner + 分类推荐 + 热销商品 |
| `/search?q=xxx` | 搜索结果 | 商品列表 |
| `/category/{id}` | 分类商品 | 按分类筛选 |
| `/product/{id}` | 商品详情 | 图片轮播 + 规格 + 加购物车 |
| `/cart` | 购物车 | 商品列表 + 金额汇总 |
| `/checkout` | 结算页 | 选择地址 + 确认下单 |
| `/orders` | 订单列表 | 按状态筛选 |
| `/orders/{id}` | 订单详情 | 商品/金额/状态 |
| `/user/profile` | 个人资料 | 修改信息 |
| `/user/addresses` | 地址管理 | 增删改 |
| `/login` | 登录 | - |
| `/register` | 注册 | - |

AI 客服悬浮按钮固定在右下角，所有前台页面可用。

### 管理后台 (`/admin`)

| 路由 | 页面 |
|------|------|
| `/admin` | 数据概览（统计卡片 + 图表） |
| `/admin/products` | 商品列表 + 新增/编辑/删除/上下架 |
| `/admin/categories` | 分类管理 |
| `/admin/orders` | 订单列表 + 状态操作 |
| `/admin/orders/{id}` | 订单详情 |
| `/admin/users` | 用户列表 + 禁用/启用 |
| `/admin/knowledge` | 知识库文档 CRUD |

前台和后台为两个独立构建入口，共享 Element Plus 组件库。

## 7. AI 智能客服设计

### RAG 流程

```
用户提问 → Embedding向量化 → ChromaDB相似度检索(Top-K=3)
    → 构建Prompt(系统指令+检索内容+用户问题)
    → DeepSeek LLM 生成 → SSE流式推送给前端
```

### 关键配置

| 组件 | 选型 | 说明 |
|------|------|------|
| 大模型 | `deepseek-chat` | 通过 `ChatOpenAI` 适配，`base_url` 指向 DeepSeek API |
| Embedding | DeepSeek Embedding 或 `bge-large-zh` | 中文语义效果好 |
| 向量库 | ChromaDB | 轻量，Python 原生，零配置 |
| 文档分割 | `RecursiveCharacterTextSplitter` | chunk_size=500, overlap=50 |
| Prompt | `ChatPromptTemplate` | 系统角色 + 知识库上下文 + 用户问题 |

### 知识库文档分类

- 产品问题（参数、功能、库存等）
- 订单问题（下单流程、支付方式、物流查询等）
- 退换货问题（退货政策、换货流程、退款时效等）
- 其他（平台规则、活动说明等）

### 降级策略

当检索相似度低于阈值(0.7)或无匹配时，回复："抱歉，我暂时无法回答这个问题，建议您联系人工客服获取帮助。"

## 8. 项目目录结构

```
online-mall-system/
├── frontend/               # Vue3 商城前台
│   ├── src/
│   │   ├── views/          # 页面组件
│   │   ├── components/     # 通用组件 + AI客服聊天组件
│   │   ├── stores/         # Pinia 状态管理
│   │   ├── api/            # 后端接口封装
│   │   ├── router/         # 路由配置
│   │   └── assets/         # 静态资源
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── admin/                  # Vue3 管理后台 (独立入口)
│   ├── src/
│   │   ├── views/          # 管理页面
│   │   ├── components/     # 管理组件
│   │   ├── stores/
│   │   ├── api/
│   │   ├── router/
│   │   └── assets/
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── main.py         # 应用入口
│   │   ├── api/            # 路由 + 接口函数
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── products.py
│   │   │   ├── cart.py
│   │   │   ├── orders.py
│   │   │   ├── ai_chat.py
│   │   │   └── admin.py
│   │   ├── models/         # SQLAlchemy 数据模型
│   │   │   ├── user.py
│   │   │   ├── product.py
│   │   │   ├── order.py
│   │   │   └── knowledge.py
│   │   ├── schemas/        # Pydantic 请求/响应模型
│   │   ├── services/       # 业务逻辑层
│   │   ├── core/           # 配置、安全、依赖注入
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── deps.py
│   │   └── ai/             # LangChain RAG 模块
│   │       ├── rag.py      # RAG 管道
│   │       ├── loader.py   # 文档加载与切分
│   │       ├── vectorstore.py # 向量存储
│   │       └── prompts.py  # Prompt 模板
│   ├── static/             # 商品图片存储
│   ├── requirements.txt
│   └── alembic/            # 数据库迁移
└── docs/                   # 设计文档 + SQL 初始化脚本
    └── superpowers/
        └── specs/
```

## 9. 非功能需求

- **安全性**: JWT 认证、密码 bcrypt 哈希、SQL 注入防护(SQLAlchemy ORM)、CORS 配置
- **性能**: 商品列表分页(默认20条/页)、图片上传限制(2MB)、数据库索引优化
- **可维护性**: 前后端分离、API 版本化(`/api/v1`)、业务逻辑与路由分离(Service层)

## 10. 开发顺序

1. 后端骨架 — FastAPI 项目结构 + 数据库模型 + 基础配置
2. 前端框架 — Vue3 + Vite + Element Plus 项目初始化（前台 + 后台两个入口）
3. 商品模块 — 后端 API + 前端商城首页、商品列表、商品详情
4. 用户模块 — 注册/登录 + JWT + 用户中心 + 地址管理
5. 购物车 & 订单 — 购物车 CRUD + 下单流程 + 订单管理
6. 管理后台 — 数据统计 + 商品/分类/订单/用户管理
7. AI 智能客服 — LangChain RAG 管道 + DeepSeek 集成 + 前端聊天组件
8. 优化 & 收尾 — 样式完善、错误处理、初始化数据、文档
