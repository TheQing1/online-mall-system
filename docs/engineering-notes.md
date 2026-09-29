# 工程笔记

README 只回答两件事：**这是什么**、**怎么跑起来**。

这份文件放那些不该占着门面、但也不想丢掉的东西：设计取舍、部署与运维的具体做法、
踩过的坑、以及「哪些事真的验证过、哪些没有」。面向的是要改动这个项目的人
——包括几个月后的我自己。

---

## 一、部署与运维

### 1.1 为什么需要这些步骤，而不是 `compose up` 就完事

每一件都对应一个具体的失败形态，不是「最佳实践」清单：

| 补的东西 | 不补会怎么样 |
|---|---|
| `deploy/check-env.sh` | compose 对几乎每个变量都给了能跑的默认值，所以漏配不报错，只表现成「站点能开但认证形同虚设」——浏览器里完全看不出来 |
| 模型预热放在 `up -d` 之前 | 第一个访问的人替我们下载 100MB 模型；期间 backend 一直 unhealthy，`web`（`depends_on: service_healthy`）根本不会启动，看起来像「部署失败」却查不出原因 |
| `docker-compose.prod.yml` 要求密钥必须显式给值 | `JWT_SECRET_KEY` 悄悄回落到 `change-me-in-production`，任何人都能签一个管理员 token 登进后台 |
| 日志轮转（`max-size` / `max-file`） | docker 的 json 日志默认无限增长，demo 挂几个月能把 20G 系统盘写满 |
| `deploy/smoke.sh` | `/health` 只证明进程活着。「能打开但白屏」「搜索没结果」「种子数据没进库」这些它全都发现不了，而它们恰恰是最常见的翻车方式 |

### 1.2 一键脚本失败时的手动步骤

`deploy/bootstrap.sh` 本身没做任何魔法，出问题时照着敲一遍就能定位到是哪一步：

```bash
cp .env.example .env
# 手改 .env：
#   MYSQL_ROOT_PASSWORD=$(openssl rand -hex 16)
#   JWT_SECRET_KEY=$(openssl rand -hex 32)
#   API_BIND=127.0.0.1                     # 调试端口不对外
#   没有域名：WEB_BIND=0.0.0.0  WEB_HTTP_PORT=80
#   有域名：  WEB_BIND=127.0.0.1 WEB_HTTP_PORT=8080  DOMAIN=你的域名
sh deploy/check-env.sh                     # 有域名加 --tls

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

$COMPOSE build
$COMPOSE up -d mysql redis
# 迁移 + 种子数据 + 预热模型，都在这一步做完（跑在 `up -d` 之前是关键）
$COMPOSE run --rm backend sh -c \
  'alembic -c /app/alembic.ini upgrade head && python -m app.core.seed && python -m app.ai.warmup'
$COMPOSE up -d

sh deploy/smoke.sh                         # 有域名改成 BASE_URL=https://你的域名
```

有域名的版本还要给每条命令加 `-f docker-compose.tls.yml`。

### 1.3 部署这套东西验证到哪一步了

说清楚，免得当成已经万无一失：

- 镜像能不能构建出来、三层 compose 的合并结果对不对 —— **CI 每次提交验证**；
- `deploy/check-env.sh` 的判定逻辑有**反向用例**（故意喂坏配置，断言它必须被拒）
  —— **CI 每次提交验证**；
- 五个容器**一起起来、跑通全链路**：`docker compose up -d --build` 起
  mysql / redis / backend / worker / web，再用 `deploy/smoke.sh` 从真实入口走一遍
  —— **16 项全过，0 失败 0 警告**。
  这一条覆盖的是 CI 覆盖不到的部分：端到端测试跑的是 Vite 预览服务器而不是 nginx，
  所以 SPA 回退、`/admin/` 子路径、`/assets/` 长缓存、SSE 反代不缓冲，
  以及「容器里的 entrypoint 以非 root 跑迁移和播种」此前一次都没被执行过。

**还没有验证的是**：`bootstrap.sh` 在真实 Linux 服务器上的端到端执行
——开发机是 Windows，跑不了 `get.docker.com` 与 systemd 那条路径。
上面的 1.2 就是为此准备的等价手动步骤。

### 1.4 已修复的问题清单

不再列在 README 的「已知不足」里，因为已经修了：

**更早一轮**：模型缓存曾放在 Python 包内部（compose 的 volume 会遮蔽 `app/models/*.py`，
重建镜像后容器仍在跑旧代码）；`orders` 缺少覆盖「每 30 秒定时关单扫描」的索引；
后端镜像 root 运行、无 HEALTHCHECK；nginx 默认 `client_max_body_size` 为 1m
导致传图必然 413；商城前台没有全局路由守卫；`/placeholder.png` 资源缺失。

**功能补齐**：V2 迁移的 `downgrade()` 从 `pass` 变成**真实可用的回滚**
（有真实 MySQL 的 upgrade→downgrade→upgrade 往返用例守着）；上传补了**文件头（魔数）校验**，
改个后缀传脚本会被拒；限流从「只有三个接口」变成**全站兜底 + 分接口配额**；
缓存补了**击穿 / 穿透 / 雪崩**三道防护；加了 **6 条告警规则 + Grafana 看板**；
10 个端到端用例**进了 CI**。

**部署链路**：`deploy/bootstrap.sh` 一条命令从裸机到可访问（含装 Docker、生成随机密钥、
预热模型）；`deploy/check-env.sh` 把「漏配但照样能跑起来」的配置挡在启动前；
`deploy/smoke.sh` 从用户入口走一遍关键链路；`docker-compose.prod.yml` 要求密钥必须显式给值
并加日志轮转；`docker-compose.tls.yml` 用 Caddy 自动签发并续期证书。

商品图上传目录从「bind mount 到仓库里」改成命名卷——容器以 uid 1000 运行，
而宿主机那个目录归谁取决于「谁 clone 的仓库」，root clone 再 sudo 部署就写不进去，
后台传图直接 500，报错位置离原因还很远；部署自检里补了一条「真传一张图」把这类问题钉住。

**本地完整跑一遍时真踩到并修掉的**（都是 CI 一定发现不了的）：

1. `web` 的 `depends_on` 原本等 `backend: service_healthy`，而后端首次启动要下载 BGE 模型，
   慢网络下超过 `start_period` 被判成 unhealthy，compose 的处理是**直接报错退出**——
   结果是 `up -d` 失败、web 容器连创建都没创建，站点根本不存在。改成 `service_started`
   后 nginx 立刻托管前端，后端就绪前 `/api` 返回 502、好后自动恢复。
2. worker 与 backend 共用镜像，于是也继承了镜像里那条「请求 `/health`」的 HEALTHCHECK，
   但 worker 根本不跑 HTTP 服务，那条检查对它**永远失败**，`docker compose ps` 里常年挂着
   一个 (unhealthy) 纯噪音。换成「PID 1 确实是那个定时任务进程」。
3. `.dockerignore` 里的 `node_modules` 只匹配根目录，匹配不到 `frontend/node_modules`。
   本地「先 npm ci 再构建镜像」时，323MB 的 Windows 版依赖会被塞进上下文，
   再被 `COPY frontend .` 覆盖掉容器里刚装好的 Linux 版；Vite 8 的 rolldown 带平台原生
   二进制，构建当场失败。改成 `**/node_modules`，并在 CI 里放了个「假 vite」守住这条路径。
4. 后端依赖里的 torch 默认装的是 CUDA 版，顺带拖进 `nvidia-cudnn-cu13`(553MB)、cublas
   等合计 3~4GB 完全用不到的库，**镜像从 1.5GB 涨到 8GB 左右**。项目本来就把模型跑在
   CPU 上（`device="cpu"`），加一句 `--extra-index-url .../whl/cpu` 即可（实测解析结果
   是 `torch-2.14.0+cpu` 196MB）。CI 发现不了，因为 GitHub 的机器下载快、磁盘也大。

**商品数据的两处问题**，都是「只有真打开页面才看得见」：

1. 商品图**张冠李戴**——上一版种子里 `IMG` 的键名和图片内容完全对不上
   （`phone_1` 是 AirPods、`watch` 是冰箱广告、`tea` 是手机照片），
   17 个商品里只有 1 个图是对的。根因是「给图片起了想象中的名字」，
   映射写错了不会有任何报错。现在图片文件名就是商品 slug，文件名即事实。
2. 商品详情页**分类显示「未分类」**——列表接口会给 `category_name` 赋值，详情接口漏了，
   同一个字段两条路径行为不一致，前端就回落成了默认文案。

---

## 二、可观测性

后端在 `/metrics` 暴露 Prometheus 指标（nginx 没有反代它，只对本机/监控网段可见）：

| 指标 | 用途 |
|---|---|
| `http_requests_total{method,path,status}` | 按**路由模板**聚合——用原始路径的话每个商品 id 都是一条时间序列，label 基数会炸 |
| `http_request_duration_seconds` | 延迟直方图，算 P95 / P99 |
| `cache_operations_total{result}` | 命中 / 未命中 / 写入 / 负缓存：看缓存到底有没有在起作用 |
| `rate_limit_blocked_total{scope}` | 被限流拦截的次数：既看滥用，也看「配额是不是配紧了误伤正常用户」 |
| `redis_up` | Redis 是否可用（0 = 已降级为无缓存、不限流） |
| `background_task_runs_total{task,result}` | 定时任务执行 / 跳过 / 失败——关单失败会直接导致库存不回补 |

配上 6 条告警规则（5xx 比例、P99 超 1 秒、Redis 降级、限流激增、定时任务失败、
十分钟没有流量）和一块 Grafana 看板：

```bash
docker compose --profile observability up -d
# Grafana http://localhost:3000（admin/admin）里会自动出现「Online Mall · API 概览」看板
```

**为什么自己用 `prometheus_client` 写指标，而不是 `prometheus-fastapi-instrumentator`**：
后者 8.x 要求 `starlette>=1.0`，与本项目锁定的 FastAPI 0.115（要求 `<0.39`）冲突，
装上 `pip check` 直接报依赖不一致。自己写不到 60 行，还能**复用访问日志里已经算好的耗时**
（计时只做一次，两个消费者）。

---

## 三、核心设计说明

- **SKU 化交易**：购物车/订单按 SKU 计价扣库存，商品表 `price/stock` 为聚合展示值。
- **搜索**：查询理解单独成层（`app/services/search.py`），把「用户敲的字」和「文案写的字」
  对齐。三类差异各有对策——**形式差异**（空格、连字符、大小写、全角、容量单位写法
  `512G`/`512GB`）由统一归一化管道消除，查询侧和文案侧走同一个 `normalize()`；
  **分词差异**用 jieba 把中文长词切开（「华为手机」→ 华为 + 手机）；**用词差异**
  （「鞋子」vs「运动鞋」、「苹果」vs iPhone）没有算法能推，只能靠数据，单独放在
  `search_synonyms.py` 里维护。词间 AND，只有 AND 一条都没有时才退化为 OR，
  避免「一个词不认识就整页空白」。覆盖商品名、描述、分类名与 SKU 名称，默认按名称命中数排序。
  代价：`%keyword%` 用不到索引，数据量大要换成物化搜索列或搜索引擎。
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
- **商品数据与逻辑分离**：商品与分类数据在 `app/core/catalog.py`，写库逻辑在
  `app/core/seed.py`。商品表一长（现在 59 个商品 / 130 个 SKU），混在一个文件里就没人愿意改了。
- **支付扩展点**：当前为页面化模拟收银台（`POST /orders/{id}/pay`）。接微信/支付宝时
  只需把该端点换成「创建支付单 + 异步回调校验」，订单表已预留 `paid_at/refund_*` 等字段。

> `backend/data/`（可用环境变量 `DATA_DIR` 覆盖）刻意放在 Python 包**外面**：
> 早期向量库与模型缓存位于 `app/` 内部，而 compose 用 named volume 挂载同一路径，
> 会把 `app/models/*.py` 一起遮蔽——重建镜像后容器里跑的仍是 volume 中的旧代码。

---

## 四、性能与压测：怎么读那张表

README 里那张表要这样读：**吞吐几乎没变，但延迟（尤其尾部）几乎减半。**
原因是 50 并发对单 worker + 本地 MySQL 来说远没到瓶颈——瓶颈在 CPU 与连接池，
不在数据库。想看出吞吐差异得压到更高并发，或者换成更重的查询。
**缓存的价值在这里体现为延迟与尾延迟，不是吞吐**；把结论说成「缓存让 QPS 翻倍」就是不诚实的。

另外两个诚实的边界：

- 压测**没有包含登录与下单**：登录按 IP 限流（10 次/分钟），压测会直接撞 429，
  那是限流器的性能而不是业务的性能；下单是有状态写路径，混在一起测没有解释力。
  想压写路径请单独写用户类并调大限额，脚本注释里写了做法。
- 单 worker 单机，**不代表生产容量**——它证明的是「加了这些之后没有把读路径拖慢」，
  以及缓存确实在起作用。

---

## 五、RAG 评测抓出来的三个坑

先说两个决策：

- **为什么重排默认关闭**：它首次使用要多下载 1.1GB 的 `bge-reranker-base`，之后每条
  问题在 CPU 上多花约 0.6 秒（10 条候选，实测）。收益是 recall@3 从 98% 到 100%、
  recall@1 再提 2 个百分点——值不值取决于场景，所以做成一个开关
  （`RAG_RERANK_ENABLED=true`），而不是替使用者决定。
- **融合权重 0.6/0.4 是怎么来的**：扫过 5 组（向量/BM25 从 0.7/0.3 到 0.3/0.7），
  0.6/0.4 在 recall@1 与 recall@3 上同时最优。
  `test_hybrid_retrieval_is_not_worse_than_vector` 就是防止后续调参把它调坏的回归用例。

都是被评测用数据抓出来的，不是看文档看出来的：

- `BM25Okapi` 的 IDF 在「某个词出现在超过一半文档里」时是**负数**，于是命中了这个词的
  文档得分反而低于完全没命中的文档（小语料上尤其致命，而本项目的知识库刚好充满
  「商品」「订单」「配送」这类高频词），因此改用 IDF 恒非负的 `BM25Plus`；
- 评测脚本用 `"bge" in 路径` 去模型缓存里找 Embedding 模型，而新下载的重排模型
  `bge-reranker-base` 也含 "bge"，于是**重排模型被当成 Embedding 加载**，
  向量召回从 84.3% 直接掉到 3.9%。这类「命名撞车」在缓存目录里非常隐蔽，
  现在改成精确匹配模型目录；
- BGE **v1.5 不需要** query 指令前缀（那是 v1 的要求），加上反而使平均余弦距离
  从 0.357 劣化到 0.401，因此代码中刻意不加，详见 `app/ai/vectorstore.py` 注释。

> 评测集从 20 条扩到 51 条、文档从 10 篇扩到 22 篇并加入近义干扰文档之后，
> 纯向量的绝对分数比早期版本低——这是评测变难的正常结果，也让「混合检索到底值不值」
> 有了可比的数据。

---

## 六、前端产物体积优化的代价

Element Plus 改成按需引入后（`unplugin-vue-components` + `ElementPlusResolver`），
两个前端的 `dist` 从 1579KB / 1600KB 降到 **762KB / 797KB**，
主 chunk 从 777KB / 1167KB 降到 103KB / 517KB。

代价是三个地方要自己处理：服务式组件（`ElMessage`/`ElMessageBox`）与指令（`v-loading`）
不走模板解析、插件管不到，样式要显式引；中文 locale 也要从
`app.use(ElementPlus, { locale })` 改成 `<el-config-provider>`。
这三件事都由端到端测试守着。

---

## 七、测试怎么组织

**默认 96 个用例完全自包含**：不需要 MySQL、Redis、联网——用例跑在 SQLite 上，
向量部分使用确定性假 Embedding、重排用桩模型。CI 里额外跑 `ruff check` 与覆盖率。

另外 **17 个用例需要真实基础设施**，连不上时自动 skip、不会让 CI 变红
（CI 里由 `infra-integration` 任务起真容器跑，并且「被 skip 就判定失败」）：

```bash
cd backend && pytest -m mysql -v    # 并发防超卖 / 幂等支付 / 外键 / InnoDB 校验 / 迁移回滚
cd backend && pytest -m redis -v    # 缓存三层防护 / 限流配额 / 分布式锁互斥
```

按模块运行：

```bash
pytest tests/test_security.py -v        # 越权与鉴权
pytest tests/test_regressions.py -v     # 已修复缺陷的回归
pytest -m rag_quality -s                # 真实 BGE 模型的召回率（无模型缓存时自动 skip）
```

端到端覆盖范围：注册/登录/JWT、商品列表/详情/SKU、购物车库存校验（含累加上限）、
下单 → 支付 → 发货 → 确认收货 → 退款全流程、取消回补库存、订单超时自动关单、
会话越权（403）、管理端鉴权、知识库增量索引、RAG 召回率评测，
以及**真实 InnoDB 上的多线程并发防超卖**与**并发支付幂等性**。

> 本地跑端到端之前要把后端限流配额调大：全站兜底是 300/分，登录是 10/分，
> 而一轮 E2E 要发几十个请求、登录 3 次，连跑几轮就会自己撞上 429。
> 这不是 bug，是限流真的在生效——测试环境的正确做法是放宽配额：
> `RATE_LIMIT_API=0 RATE_LIMIT_LOGIN=1000 uvicorn app.main:app --port 8000`。

---

## 八、升级说明（V1 → V2）

- 引入 Alembic，移除应用启动时 `create_all`；
- 新增 `product_skus / banners / favorites / chat_sessions / chat_messages / eval_test_cases`；
- `cart_items / order_items` 增加 SKU 维度，`orders` 增加支付/退款字段；
- 支付改为真实"待支付"流程 + 后台 30s 轮询自动关单；
- Chroma 改用原生客户端（移除与新版冲突的 `langchain-chroma`）。

> 老库升级：`cd backend && alembic upgrade head` 会自动补列并对存量商品/购物车/订单回填默认 SKU。
