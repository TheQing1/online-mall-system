# Online Mall —— 基于 LangChain 的 AI 智能客服商城系统（V2）

[![CI](https://github.com/TheQing1/online-mall-system/actions/workflows/ci.yml/badge.svg)](https://github.com/TheQing1/online-mall-system/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg)](backend/requirements.txt)
[![Vue](https://img.shields.io/badge/Vue-3-42b883.svg)](frontend/package.json)

综合 B2C 在线商城，集成了基于 **LangChain + RAG + DeepSeek** 的 AI 智能客服，
并补齐了商品 SKU、页面化模拟支付、订单超时关单、退款、收藏、Banner 运营、
多轮 AI 会话、RAG 评测等完整链路。

## 亮点速览

- **防超卖**：`UPDATE ... WHERE stock >= ?` 原子条件更新 + `rowcount` 判断，
  并在**真实 MySQL/InnoDB** 上用 8 线程并发测试验证（恰好 3 单成交）；
- **订单状态机**：白名单校验流转合法性，所有流转用条件 UPDATE 做乐观并发控制，
  并发支付幂等性也在真实 InnoDB 上验证过；
- **RAG 可量化**：自建 20 条评测集（含口语化改写），实测 **recall@1 = 90%、recall@3 = 95%**，
  并有一个经 A/B 实测被否掉、已回滚的优化（BGE 指令前缀）；
- **工程化**：Alembic 幂等迁移（含可用的 downgrade）、51 个 pytest 用例（覆盖率 72%）、
  GitHub Actions CI、Docker Compose 一键部署（多阶段镜像 + 非 root + HEALTHCHECK）。

## 技术栈

| 层级 | 技术 |
|------|------|
| 商城前端 | Vue3 + Element Plus + Vite + Pinia |
| 管理后台 | Vue3 + Element Plus + Vite（独立入口，`/admin/` 子路径部署） |
| 后端 API | FastAPI + SQLAlchemy 2.0 + Pydantic v2 |
| 数据库 | MySQL 8.0（Alembic 迁移管理，14 张表） |
| 向量存储 | ChromaDB（原生客户端，本地持久化） |
| AI 框架 | LangChain 0.3.x（RAG：切片 → BGE Embedding → 检索 → 生成） |
| Embedding | BGE `bge-small-zh-v1.5`（本地部署，ModelScope 下载） |
| 大模型 | DeepSeek（OpenAI 兼容接口，模型名 `deepseek-flash`） |
| 认证 | JWT（python-jose + bcrypt） |
| 部署 | Docker Compose + Nginx（多阶段构建、非 root、HEALTHCHECK、自动迁移 + 种子数据） |
| 测试 | pytest + httpx（51 个用例：认证/订单全流程/越权/回归/RAG 召回/真实 MySQL 并发） |
| 质量 | ruff + pytest-cov + ESLint + Prettier + GitHub Actions |

## 功能概览

### 商城前台
- 首页：Banner 运营位（后台可管理）+ 分类 + 热销推荐
- 商品：多规格 SKU（独立价格/库存）、收藏、详情图片
- 购物车：按 SKU 加购/改数量/删除、总价计算
- 下单：选地址 → 确认订单（SKU 快照）→ 待支付
- 支付：页面化模拟收银台（下单 30 分钟未支付自动关单并回补库存）
- 订单：取消、确认收货、申请退款（退款原因/审核流转/库存销量回滚）
- 用户：注册/登录、地址管理、我的订单、我的收藏
- AI 客服：多轮会话（历史持久化）、检索改写、商品推荐卡片、快捷问题

### 管理后台
- 数据看板：用户/订单/销售额/退款待处理
- 商品管理：CRUD + 上/下架 + 多 SKU 规格/价格/库存编辑
- 分类 / 用户管理
- 订单管理：按状态/单号筛选、状态流转、详情、退款审核（同意/驳回）
- Banner 管理：运营位增删改、上下线、排序
- 知识库：文档 CRUD + 批量导入 .md/.txt（增量同步向量索引）
- RAG 评测：测试用例管理 + 一键评测召回命中率

## 快速开始（开发环境）

### 1. 数据库

MySQL 8.0 建库并升级表结构：

```bash
cd backend
cp .env.example .env        # 如有 .env 直接修改
alembic upgrade head        # 迁移：老库自动补列/回填 SKU，新库自动建表
python -m app.core.seed     # 种子数据：admin/demo 账号、商品、Banner、知识库
```

> 首次运行会自动通过 ModelScope 下载本地 Embedding 模型（约 100MB）。

### 2. 启动后端

```bash
cd backend
uvicorn app.main:app --reload --port 8000
# API 文档: http://localhost:8000/docs
```

### 3. 启动前端

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
cd admin    && npm install && npm run dev   # http://localhost:5174/admin/login
```

## Docker 一键启动（推荐演示）

```bash
# 可选：准备 .env 配置 DeepSeek Key
DEEPSEEK_API_KEY=sk-xxx docker compose up -d --build

# 服务就绪后访问
# 商城:  http://localhost
# 管理:  http://localhost/admin/login
# API:   http://localhost:8000/docs
```

Web 容器会自动执行 `alembic upgrade head` → 种子数据 → 启动 API；
Nginx 负责 `/api`、`/static` 反代与两个 SPA 静态托管。

## 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |
| 演示用户 | demo | demo123 |

## 环境变量（backend/.env）

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=online_mall

JWT_SECRET_KEY=your-secret-key-change-me
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
ORDER_EXPIRE_MINUTES=30

DEEPSEEK_API_KEY=sk-your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash

UPLOAD_DIR=static/products
MAX_UPLOAD_SIZE=2097152
```

> 完整清单见 `backend/.env.example`。`backend/.env` 含真实密钥，已被 `.gitignore` 忽略，
> 请勿提交或打包外发。

## 项目结构

```
├─ frontend/            # 商城前台 (Vite :5173)
├─ admin/               # 管理后台 (Vite :5174，生产构建至 /admin/)
├─ backend/
│  ├─ app/api           # 路由层（REST + SSE）
│  ├─ app/services      # 业务层
│  ├─ app/models        # SQLAlchemy 模型（14 张表）
│  ├─ app/ai            # RAG 链路（loader/vectorstore/indexer/rag/eval_dataset）
│  ├─ app/core          # 配置/安全/数据库/后台任务
│  ├─ alembic           # 数据库迁移
│  ├─ tests             # 51 个 pytest 用例
│  └─ data/             # 运行时生成：向量库 + Embedding 模型缓存（已 gitignore）
├─ docs/interview-qa.md # 面试问答（与代码同步维护）
├─ .github/workflows    # CI
├─ web/                 # Nginx + 前端产物 Dockerfile
└─ docker-compose.yml
```

> `backend/data/`（可用环境变量 `DATA_DIR` 覆盖）刻意放在 Python 包**外面**：
> 早期向量库与模型缓存位于 `app/` 内部，而 compose 用 named volume 挂载同一路径，
> 会把 `app/models/*.py` 一起遮蔽——重建镜像后容器里跑的仍是 volume 中的旧代码。

## 已知不足

诚实地列在这里，避免面试时被动：

- 前端无 TypeScript、无单元测试；商城前台的全局路由守卫已是唯一权威判断，
  但各页面里还留着早期手写的 `onMounted` 登录判断（现在属于冗余代码，可删）；
- `alembic downgrade` 只有索引迁移是真实可用的；V2 那个大迁移的 `downgrade()` 仍是
  `pass`（命令成功退出但什么都不回滚），需要补齐；
- JWT 存 localStorage；无限流、无 refresh token；部署为 HTTP，无 HTTPS，
  安全响应头已配但 HSTS 仍注释着（等 HTTPS 终结后再开）；
- compose 把 backend 的 8000 端口直接映射到宿主机（方便用 `/docs` 调试），
  因此 entrypoint 里的 `--forwarded-allow-ips='*'` 是有折扣的信任：
  能直连 8000 的客户端可以伪造 `X-Forwarded-For`。生产应去掉该端口映射，
  或把 `*` 收紧成 nginx 所在网段；
- 多副本部署时超时关单任务会在每个副本各跑一份，需要分布式锁；
- 模型缓存首次启动需联网从 ModelScope 下载（约 100MB）；
- 上传只校验扩展名、不校验文件魔数；商品图存本地盘，生产应上对象存储。

> 已修复、因此不再列在上面的：模型缓存曾放在 Python 包内部（compose 的 volume 会遮蔽
> `app/models/*.py`，重建镜像后容器仍在跑旧代码）；`orders` 缺少覆盖「每 30 秒定时关单
> 扫描」的索引；后端镜像 root 运行、无 HEALTHCHECK；nginx 默认 `client_max_body_size`
> 为 1m 导致传图必然 413；商城前台没有全局路由守卫；`/placeholder.png` 资源缺失。

## 运行测试

```bash
python -m venv .venv
.venv\Scripts\pip install -r backend/requirements-dev.txt   # Windows
cd backend
../.venv/Scripts/python -m pytest
```

**默认 47 个用例完全自包含**：无需 MySQL、无需联网——用例跑在 SQLite 上，
向量部分使用确定性假 Embedding。CI 里额外跑 `ruff check` 与覆盖率。

另外 4 个用例需要真实 MySQL（并发防超卖 + 幂等支付 + 外键 + InnoDB 校验），
连不上时自动 skip，不会让 CI 变红：

```bash
cd backend && pytest -m mysql -v          # 需要本地 MySQL；会自动建/删 <库名>_test
```

按模块运行：

```bash
pytest tests/test_security.py -v        # 越权与鉴权
pytest tests/test_regressions.py -v     # 15 个已修复缺陷的回归
pytest -m rag_quality -s                # 真实 BGE 模型的召回率（无模型缓存时自动 skip）
pytest -m mysql -v                      # 真实 MySQL / InnoDB 集成（连不上时自动 skip）
```

覆盖范围：注册/登录/JWT、商品列表/详情/SKU、购物车库存校验（含累加上限）、
下单 → 支付 → 发货 → 确认收货 → 退款全流程、取消回补库存、订单超时自动关单、
会话越权（403）、管理端鉴权、知识库增量索引、RAG 召回率评测，以及
**真实 InnoDB 上的多线程并发防超卖**与**并发支付幂等性**。

### 在真实 MySQL 上验证过的并发结论

`tests/test_mysql_integration.py` 在 MySQL 8.0.43 上实测：

| 场景 | 结果 |
|------|------|
| 8 线程并发抢 3 件库存 | 恰好 3 单成功，SKU 与商品聚合库存同时归零 |
| 同一订单 5 次并发支付 | 恰好 1 次成功，销量只累加 1 |
| 删除已被下单的商品 | 抛出 IntegrityError（证明服务层的拦截是必要的） |

失败的线程只接受 `库存不足 / 状态不允许` 这种业务错误；其他异常一律抛出，
避免「恰好 3 单成功」是因为别的原因失败而侥幸通过。

### RAG 召回率（真实模型实测）

`tests/test_rag_quality.py` 加载真实的 `bge-small-zh-v1.5`，对 10 篇知识文档建索引，
按生产同款参数（余弦距离 ≤ 0.7、top-3）在 **20 条评测用例**（一半为口语化改写）上评测：

| 指标 | 数值 |
|------|------|
| recall@1 | 90% |
| recall@3（生产取值） | 95% |
| recall@10 | 100% |

> 评测集规模有限，该数字应视为冒烟测试而非基准。另外实测确认：
> BGE **v1.5 不需要** query 指令前缀（那是 v1 的要求），加上反而使平均余弦距离
> 从 0.357 劣化到 0.401，因此代码中刻意不加，详见 `app/ai/vectorstore.py` 注释。

## 代码质量

```bash
cd backend && ruff check .                      # 静态检查（F/E9：只拦真 bug）
cd backend && pytest --cov=app --cov-report=term-missing   # 当前 72%，CI 门槛 70%

cd frontend && npm run lint && npm run build    # 两个前端都需 lint + 构建通过
cd admin    && npm run lint && npm run build
```

ESLint / Prettier 配置与依赖都已就位（`eslint.config.mjs` / `.prettierrc` +
`devDependencies`），`npm run lint` 与 `npm run format` 直接可用，CI 里也会跑 lint。
规则只开「正确性」、不引格式规则，格式交给 Prettier，避免两套工具互相打架。

## 核心设计说明

- **SKU 化交易**：购物车/订单按 SKU 计价扣库存，商品表 `price/stock` 为聚合展示值。
- **防超卖**：扣减用 `UPDATE ... WHERE stock >= ?` 原子条件更新，以 `rowcount` 判断成败，
  无需额外加锁；SKU 与商品聚合库存同一事务内扣减。
- **订单状态机**：`pending_pay → paid → shipped → completed`；待支付可取消；
  `paid/shipped/completed` 可申请退款 → `refunding → refunded`；管理端驳回则回到原状态。
  管理端流转受白名单约束，且所有流转都用 `UPDATE ... WHERE status = ?` 做乐观并发控制，
  避免并发重复支付导致销量重复累加、以及自动关单误杀已支付订单。
- **事务原子性**：下单流程（扣库存 + 建订单 + 清空购物车）在**同一个事务**内提交，
  `clear_cart(commit=False)` 不再中途 commit。
- **AI 多轮 RAG**：会话历史存 `chat_sessions/chat_messages`；每轮先做 Query 改写再检索；
  无知识命中时检索商品库并推送商品卡片；回答以 SSE JSON 帧流式返回。
  会话接口有归属校验（他人会话 403、不存在 404），匿名会话可被登录用户认领。
- **增量索引**：知识文档增删改只重建该文档对应向量，不再全量重建。
- **支付扩展点**：当前为页面化模拟收银台（`POST /orders/{id}/pay`）。接微信/支付宝时
  只需把该端点换成「创建支付单 + 异步回调校验」，订单表已预留 `paid_at/refund_*` 等字段。

## 升级说明（V1 → V2）

- 引入 Alembic，移除应用启动时 `create_all`；
- 新增 `product_skus / banners / favorites / chat_sessions / chat_messages / eval_test_cases`；
- `cart_items / order_items` 增加 SKU 维度，`orders` 增加支付/退款字段；
- 支付改为真实“待支付”流程 + 后台 30s 轮询自动关单；
- Chroma 改用原生客户端（移除与新版冲突的 `langchain-chroma`）。

> 老库升级：`cd backend && alembic upgrade head` 会自动补列并对存量商品/购物车/订单回填默认 SKU。
