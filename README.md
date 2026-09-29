# Online Mall —— 基于 LangChain 的 AI 智能客服商城系统

[![CI](https://github.com/TheQing1/online-mall-system/actions/workflows/ci.yml/badge.svg)](https://github.com/TheQing1/online-mall-system/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg)](backend/requirements.txt)
[![Vue](https://img.shields.io/badge/Vue-3-42b883.svg)](frontend/package.json)

前后端分离的 B2C 在线商城，交易闭环完整（多规格 SKU → 下单 → 模拟支付 → 发货 → 退款审核），
并集成了一个基于 **LangChain + RAG + DeepSeek** 的 AI 智能客服：本地 BGE 向量化、
向量 + BM25 混合检索、可选交叉编码器重排、SSE 流式回答。

## 亮点速览

- **并发正确性**：库存扣减用 `UPDATE ... WHERE stock >= ?` 原子条件更新 + `rowcount`
  判断；在**真实 MySQL/InnoDB** 上实测 8 线程抢 3 件库存恰好成交 3 单、同一订单
  5 次并发支付恰好成功 1 次。
- **检索效果可量化**：自建 22 篇知识文档 + **51 条评测集**，在同一套评测、同一条线上
  代码路径上测出三级提升：纯向量 recall@1 84.3% → BM25 混合检索 90.2% →
  加交叉编码器重排 **92.2%，且 recall@3 达到 100%**。
- **工程化**：113 个 pytest 用例（覆盖率 77%）+ 10 个 Playwright 端到端用例
  （真浏览器、断言控制台零报错）；Alembic 迁移**可回滚**（有真实 MySQL 往返用例）；
  GitHub Actions 一条流水线跑完全部检查。
- **抗读压力与防滥用**：商品读路径走 Redis 缓存（50 并发实测 P99 51ms → **23ms**），
  击穿 / 穿透 / 雪崩各有对应防护；全站限流 + 分接口配额；关单任务用分布式锁串行化
  并拆成独立 worker；Redis 不可用时只丢缓存和限流，不影响业务。
- **交付**：一条命令从裸机部署到线上（校验配置 → 构建 → 迁移播种 → 预热模型 → 起服务 →
  自检），有域名则自动签发并续期 HTTPS 证书。

## 界面速览

| 商城首页 | 商品详情（多规格 SKU） |
|---|---|
| ![商城首页](docs/screenshots/mall-home.png) | ![商品详情](docs/screenshots/mall-product-detail.png) |

| AI 客服（多轮 + 商品卡片 + 流式输出） | 购物车 |
|---|---|
| ![AI 客服](docs/screenshots/mall-ai-chat.png) | ![购物车](docs/screenshots/mall-cart.png) |

| 管理后台 · 数据概览 | 管理后台 · 登录 |
|---|---|
| ![后台看板](docs/screenshots/admin-dashboard.png) | ![后台登录](docs/screenshots/admin-login.png) |

> 截图由 `npm run test:e2e` 的 Playwright 用例自动产出，所以不会随界面改动而过期。

## 技术栈

| 层级 | 技术 |
|------|------|
| 商城前端 | Vue3 + Element Plus（按需引入）+ Vite + Pinia |
| 管理后台 | Vue3 + Element Plus + Vite（独立入口，`/admin/` 子路径部署） |
| 后端 API | FastAPI + SQLAlchemy 2.0 + Pydantic v2 |
| 数据库 | MySQL 8.0（Alembic 迁移管理，14 张表） |
| 缓存/限流/锁 | Redis 7（不可用时自动降级为无缓存、不限流） |
| 检索 | 向量召回 + BM25（jieba 分词）加权融合，可选交叉编码器重排 |
| AI | LangChain 0.3.x · BGE `bge-small-zh-v1.5`（本地部署）· DeepSeek |
| 向量存储 | ChromaDB（原生客户端，本地持久化） |
| 可观测性 | 结构化日志 + request_id + Prometheus + Grafana + 告警规则 |
| 部署 | Docker Compose + Nginx（多阶段构建、非 root、HEALTHCHECK、自动迁移 + 种子数据） |
| 质量 | pytest + httpx + Playwright + ruff + ESLint + GitHub Actions |

## 功能概览

**商城前台**

- 首页：Banner 运营位（后台可管理）+ 分类导航 + 热销推荐
- 商品：多规格 SKU（独立价格/库存）、收藏、详情图
- 购物车 / 下单 / 页面化模拟收银台（30 分钟未支付自动关单并回补库存）
- 订单：取消、确认收货、申请退款（审核流转 + 库存销量回滚）
- 用户：注册登录、地址管理、我的订单、我的收藏
- AI 客服：多轮会话（历史持久化）、检索改写、商品推荐卡片、流式输出

**管理后台**

- 数据看板（用户 / 订单 / 销售额 / 退款待处理）、分类与用户管理
- 商品管理：CRUD + 上下架 + 多 SKU 规格/价格/库存编辑
- 订单管理：筛选、状态流转、详情、退款审核
- Banner 运营位管理；知识库文档 CRUD + 批量导入（增量同步向量索引）
- RAG 评测：测试用例管理 + 一键评测召回命中率

## 快速开始

### Docker 一键启动（推荐）

```bash
cp .env.example .env                      # 里面标了【必须改】的两项，本地随便填也行
DEEPSEEK_API_KEY=sk-xxx docker compose up -d --build

# 商城 http://localhost          管理后台 http://localhost/admin/login
# 接口文档 http://localhost:8000/docs
```

五个服务：`mysql` / `redis` / `backend`（API）/ `worker`（定时关单）/
`web`（Nginx + 两个前端产物）。首次启动会自动迁移、写入 59 个商品的种子数据，
并下载约 100MB 的 BGE 模型，等几分钟是正常的。

想再看一眼监控面板：`docker compose --profile observability up -d`
（Prometheus `:9090`，Grafana `:3000`）。

<details>
<summary>国内构建慢的话，换上 pip / npm 镜像源</summary>

镜像加速器只管「拉基础镜像」这一段，构建里的 pip / npm 下载要靠这两个参数：

```bash
docker compose build \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com
```

后端依赖里的 torch 已经钉成 CPU 版（模型本来就跑在 CPU 上），不钉的话会多下
3~4GB 用不到的 CUDA 库。即便如此，首次构建仍要下几百 MB。

</details>

### 本地开发（不用 Docker）

```bash
# 1) 数据库：MySQL 8.0 建库后迁移 + 种子数据
cd backend && cp .env.example .env
alembic upgrade head && python -m app.core.seed

# 2) 后端
uvicorn app.main:app --reload --port 8000

# 3) 两个前端
cd frontend && npm install && npm run dev    # http://localhost:5173
cd admin    && npm install && npm run dev    # http://localhost:5174/admin/
```

Redis 是可选的：不启也能跑，缓存/限流/锁会自动降级，只是性能和防滥用能力打折。
完整的环境变量清单见 `backend/.env.example`。

### 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |
| 演示用户 | demo | demo123 |

## 部署到服务器

一台能跑 Docker 的 Linux 服务器（内存 ≥ 2G）就够了，有域名则自动配 HTTPS：

```bash
git clone https://github.com/TheQing1/online-mall-system.git && cd online-mall-system
sudo bash deploy/bootstrap.sh
```

脚本会依次做完：装 Docker → 生成随机数据库口令与 JWT 密钥 → 校验配置 → 构建镜像 →
起 MySQL/Redis → 迁移与种子数据 → 预热 Embedding 模型 → 起全部服务 → 跑一遍部署自检。
也可以无人值守：

```bash
DOMAIN=mall.example.com DEEPSEEK_API_KEY=sk-xxx sudo -E bash deploy/bootstrap.sh
```

不填 `DOMAIN` 就是 HTTP 模式（用 `http://服务器IP` 访问）；填了则由 Caddy 自动向
Let's Encrypt 申请并续期证书，前提是域名已解析到本机且 80/443 可从公网访问。

部署完可以随时自检或重置演示数据：

```bash
BASE_URL=https://你的域名 sh deploy/smoke.sh   # 从用户入口走一遍关键链路
sudo bash deploy/reset-demo.sh                # 被写乱后一键恢复初始数据
```

> 部署这套东西的设计取舍、踩过的坑、以及「哪些环节真的验证过」，
> 都写在 [`docs/engineering-notes.md`](docs/engineering-notes.md)。

## 实测结果

**并发正确性**（`pytest -m mysql -v`，MySQL 8.0 真实 InnoDB）

| 场景 | 结果 |
|------|------|
| 8 线程并发抢 3 件库存 | 恰好 3 单成功，SKU 与商品聚合库存同时归零 |
| 同一订单 5 次并发支付 | 恰好 1 次成功，销量只累加 1 |
| 删除已被下单的商品 | 抛出 IntegrityError（证明服务层的拦截是必要的） |

失败的线程只接受 `库存不足 / 状态不允许` 这种业务错误，其他异常一律抛出，
避免「恰好 3 单成功」是因为别的原因失败而侥幸通过。

**RAG 召回率**（`pytest -m rag_quality -s`，真实 BGE 模型，22 篇文档 / 51 条用例）

| 检索策略 | recall@1 | recall@3（进 Prompt 的 top-3） |
|----------|----------|------------------------------|
| 纯向量 | 84.3% | 94.1% |
| **向量 + BM25 融合（当前默认）** | **90.2%** | **98.0%** |
| 再加交叉编码器重排（`RAG_RERANK_ENABLED=true`） | **92.2%** | **100%** |

**读路径压测**（`locust -f backend/loadtest/locustfile.py`，50 并发 / 30 秒 / 单 worker）

| 指标 | 关闭 Redis 缓存 | 开启 Redis 缓存 |
|---|---|---|
| 总请求数 / 失败数 | 4455 / 0 | 4547 / 0 |
| 中位数 | 8 ms | **5 ms** |
| P95 | 25 ms | **11 ms** |
| P99 | 51 ms | **23 ms** |

省下来的是延迟与尾延迟，不是吞吐——50 并发还没压到单 worker 的瓶颈。
这三张表的解读方式、以及各自不覆盖什么，见
[`docs/engineering-notes.md`](docs/engineering-notes.md)。

## 运行测试

```bash
cd backend && pip install -r requirements-dev.txt
pytest                                    # 96 个自包含用例：不需要 MySQL / Redis / 联网
pytest -m "mysql or redis" -v             # 17 个集成用例：真实 MySQL 与 Redis
pytest --cov=app --cov-report=term-missing
ruff check .                              # 静态检查

cd frontend && npm run lint && npm run build
cd admin    && npm run lint && npm run build
```

端到端用例跑在**生产构建产物**上，覆盖首页渲染、商品详情、搜索、登录、购物车、
AI 客服面板、后台登录与看板，并断言**控制台没有任何报错**——组件没注册、
`v-loading` 指令没注册、资源 404、按需引入后样式没进来，都是它抓出来的。

```bash
# 需要先起三个服务：后端 :8000（配额调大，否则 E2E 自己会撞上限流）、
# 商城 :5173、后台 :5174（都跑 npm run build && npm run preview）
cd frontend && npm run test:e2e
```

CI 里有一个独立的 `e2e` 任务跑这套用例（起 MySQL + Redis + API + 两个前端），
所以截图每次都会跟着重新生成。本地跑之前的环境准备见
[`docs/engineering-notes.md`](docs/engineering-notes.md) 第七节。

## 项目结构

```
├─ frontend/            # 商城前台 (Vite :5173)
├─ admin/               # 管理后台 (Vite :5174，生产构建至 /admin/)
├─ backend/
│  ├─ app/api           # 路由层（REST + SSE）
│  ├─ app/services      # 业务层（含搜索查询理解 search.py）
│  ├─ app/models        # SQLAlchemy 模型（14 张表）
│  ├─ app/ai            # RAG 链路（retriever / reranker / rag / indexer）
│  ├─ app/core          # 配置/安全/缓存/限流/锁/日志/指标/后台任务/商品目录
│  ├─ alembic           # 数据库迁移
│  ├─ tests             # 113 个 pytest 用例
│  ├─ loadtest/         # Locust 压测脚本
│  └─ static/products/  # 商品图（文件名 = 商品 slug）
├─ deploy/              # 部署脚本、配置校验、部署自检、Caddyfile
├─ docs/                # 工程笔记、面试问答、简历文案、截图
├─ web/                 # Nginx 配置 + 前端产物 Dockerfile
└─ docker-compose*.yml  # 基线 / 生产加固 / 自动 HTTPS
```

## 已知不足

诚实地列在这里，避免面试时被动：

- 重排只在 CPU 上跑（每条问题约 0.6 秒），也没做重排结果缓存；上生产要么换 GPU，
  要么换更小的 cross-encoder；
- 前端无 TypeScript、无单元测试；端到端只覆盖「页面能用」这一层，
  组件内部逻辑仍没有单测兜着；
- JWT 存 localStorage、无 refresh token；HTTPS 取决于部署时填没填 `DOMAIN`，
  没域名就是纯 HTTP，nginx 里的 HSTS 也仍是注释状态；
- 缓存是 Redis 单级 + 进程内单飞：Redis 挂掉的降级期内读请求会直接压到 MySQL，
  多副本时单飞只在进程内生效；
- 限流是固定窗口，窗口边界可能出现两倍突发，也没有按用户等级/接口成本做差异化配额；
- 告警规则写好了，但没接通知渠道（Alertmanager / 钉钉），也没有指标长期存储；
- 模型缓存首次启动需联网从 ModelScope 下载约 100MB，网络不通就是起不来；
- 上传做了扩展名白名单 + 文件头（魔数）校验，但魔数挡不住精心构造的多格式文件；
  商品图仍存本地盘，生产应上对象存储。

## 文档

| 文件 | 内容 |
|---|---|
| [`docs/engineering-notes.md`](docs/engineering-notes.md) | 设计取舍、部署运维做法、修复记录、验证边界 |
| [`docs/interview-qa.md`](docs/interview-qa.md) | 55 个面试问答（与代码同步维护） |
| [`docs/resume-project.md`](docs/resume-project.md) | 简历描述三版 + 数字证据索引 + 负向结论 |

## 许可

[MIT](LICENSE)
