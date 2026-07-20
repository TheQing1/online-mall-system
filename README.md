# 🛒 Online Mall — 基于 LangChain 的 AI 智能客服商城系统

综合 B2C 在线商城，集成基于 **LangChain + RAG + DeepSeek** 的 AI 智能客服。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端商城 | Vue3 + Element Plus + Vite + Pinia |
| 管理后台 | Vue3 + Element Plus + Vite (独立入口) |
| 后端 API | FastAPI + SQLAlchemy + Pydantic |
| 数据库 | MySQL 8.0 |
| 向量存储 | ChromaDB |
| AI 框架 | LangChain (RAG) |
| 大模型 | DeepSeek (`deepseek-chat`) |
| 认证 | JWT (python-jose + bcrypt) |

## 项目结构

```
online-mall-system/
├── frontend/          # Vue3 商城前台 (端口 5173)
├── admin/             # Vue3 管理后台 (端口 5174)
├── backend/           # FastAPI 后端 API (端口 8000)
├── docs/              # 设计文档 + 数据库脚本
└── README.md
```

## 快速开始

### 1. 环境准备

- Python 3.11+
- Node.js 18+
- MySQL 8.0

### 2. 数据库

```bash
# 创建数据库
mysql -u root -p < docs/init.sql
```

### 3. 后端

```bash
cd backend

# 创建 .env 配置文件（参考下方的配置说明）

# 安装依赖
pip install -r requirements.txt

# 初始化种子数据
python -m app.core.seed

# 启动服务
uvicorn app.main:app --reload --port 8000
```

### 4. 前端商城

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

### 5. 管理后台

```bash
cd admin
npm install
npm run dev
# 访问 http://localhost:5174/admin/login
```

## 环境配置 (.env)

在 `backend/.env` 中配置：

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=online_mall

JWT_SECRET_KEY=your-secret-key-change-me
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

DEEPSEEK_API_KEY=sk-your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com

UPLOAD_DIR=static/products
MAX_UPLOAD_SIZE=2097152
```

> 注册 DeepSeek API Key: https://platform.deepseek.com/api_keys

## 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |

## API 文档

启动后端后访问: http://localhost:8000/docs (Swagger UI)

## 功能概览

### 商城前台
- 🏠 首页 Banner + 分类展示 + 热销推荐
- 🔍 商品搜索 + 分类筛选 + 价格/销量排序
- 🛒 购物车管理 (增删改)
- 📦 订单流程 (选地址 → 下单 → 支付模拟)
- 👤 用户注册/登录 + 个人资料 + 收货地址管理
- 🤖 **AI 智能客服** (右下角悬浮, RAG 驱动, SSE 流式回复)

### 管理后台
- 📊 数据概览 (用户数/商品数/订单数/销售额)
- 📦 商品管理 (CRUD + 上下架)
- 📂 分类管理
- 📋 订单管理 (状态变更)
- 👤 用户管理 (启用/禁用)
- 📖 知识库管理 (RAG 数据源, 自动同步向量索引)

### AI 智能客服
- 基于 LangChain RAG 管道
- ChromaDB 向量存储
- DeepSeek 大模型驱动
- SSE 流式生成回复
- 知识库文档热更新 (管理后台编辑后自动重建索引)

## 开发说明

- 前端使用 Vite 代理, 开发时自动转发 `/api` 和 `/static` 到后端
- JWT Token 存储在 localStorage, 请求时自动携带
- 管理后台使用独立 Token (`admin_token`), 路由守卫验证管理员角色
- 模拟支付: 下单后自动标记为已支付状态
