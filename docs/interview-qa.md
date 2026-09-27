# AI 智能客服商城 —— 面试问答（与代码同步）

> 配套项目：基于 LangChain + RAG + DeepSeek 的 B2C 在线商城
> 技术栈：Vue3 + Element Plus + Vite + Pinia / FastAPI + SQLAlchemy 2.0 + Pydantic v2 /
> MySQL 8.0 / ChromaDB / LangChain 0.3.x / BGE `bge-small-zh-v1.5`（本地）/ DeepSeek / JWT + bcrypt /
> Alembic / Docker Compose + Nginx / pytest（51 个用例，含真实 MySQL 与真实向量模型）

> ⚠️ **本文档的每一条回答都对照当前代码校验过。**
> 如果你改动了实现（例如换了向量库、调整了 `k` 或阈值、加了限流），
> 请同步改这里，否则会出现「照着背却把自己的项目说错」的情况——上一版就踩过这个坑。

---

## 一、项目介绍与架构

### 1. 介绍一下这个项目

一个综合 B2C 在线商城，特色是内置了基于 LangChain + RAG 的 AI 智能客服。三个端：

- **商城前台**（Vue3，:5173）：商品浏览/搜索/筛选、多规格 SKU 加购、下单、页面化收银台、订单与退款、收藏、地址、AI 客服；
- **管理后台**（Vue3，:5174，生产构建到 `/admin/`）：数据看板、商品与 SKU、分类、订单与退款审核、用户、Banner、知识库、RAG 评测；
- **后端**（FastAPI，:8000）：REST + SSE。

数据层：MySQL 存业务数据，ChromaDB 存知识向量，本地 BGE 做向量化，DeepSeek 做生成。

### 2. 整体架构

```
商城前台(5173)   管理后台(5174, /admin/)
      \              /
       FastAPI :8000  (REST + SSE)
      /      |       \
  MySQL   ChromaDB   DeepSeek API
 (14 张表) (向量库)   (生成)
              ^
        本地 BGE Embedding
```

- 前后端分离：前端可静态托管，后端无状态、可水平扩展；
- 商城与后台分离：两个独立 Vite 工程，Token 分开存（`token` / `admin_token`），路由守卫独立；
- 后端分层：`api`（路由）→ `services`（业务）→ `models`（ORM），`schemas` 做入参/出参校验，`ai` 收敛 RAG 相关代码。

### 3. 为什么选 FastAPI

- ASGI + 原生 async，和 LLM 流式输出（SSE）天然契合；
- Pydantic v2 自动校验 + 自动生成 Swagger（`/docs`）；
- `Depends` 让认证、DB 会话这类横切逻辑干净复用；
- 对比：Django 太重且 ORM/Admin 耦合，Flask 偏同步、生态偏旧。

### 4. 后端怎么分层，为什么

`api/` 只做参数校验、调用 service、返回结果；`services/` 承载业务规则（下单、库存扣减、状态流转、索引同步）；`models/` 是 SQLAlchemy 模型；`schemas/` 是 DTO；`core/` 放配置、DB、安全、依赖、后台任务。

好处：接口薄、逻辑可复用（前台与后台共用 `order_service`）、可测试。**这也是能写出 51 个测试的前提**——业务逻辑不依赖 FastAPI 的请求对象。

### 5. 你的具体贡献

从零搭建前后端骨架、14 张表建模、全部后端 API、订单状态机与防超卖、RAG 链路与评测、Docker Compose 部署、pytest 测试与 CI。

---

## 二、数据库与后端细节

### 6. 表怎么设计的

**14 张表**：

| 分组 | 表 |
|---|---|
| 用户 | `users`、`addresses`、`favorites` |
| 商品 | `categories`、`products`、`product_skus` |
| 交易 | `cart_items`、`orders`、`order_items` |
| 运营 | `banners` |
| AI | `knowledge_docs`、`chat_sessions`、`chat_messages`、`eval_test_cases` |

关键约束与选择：

- 金额统一 `DECIMAL(10,2)`，**不用 float**；
- `product_skus` 唯一 `(product_id, name)`；`cart_items` 唯一 `(user_id, sku_id)`；`favorites` 唯一 `(user_id, product_id)`；
- `orders.order_no` 唯一 + 索引；`chat_sessions.id` 用 UUID 字符串（前端生成，支持匿名会话）；
- 商品图片、地址快照、SKU 规格用 JSON 列。

### 7. 为什么订单里存快照

下单时把 `address_snapshot`（收货人/电话/省市区/详址）和订单项里的 `product_name`、`product_image`、`sku_name`、`sku_spec`、`price` 冗余保存。

用户之后改地址、改商品名、下架甚至改价，都不影响历史订单——订单是交易凭证，必须能还原下单那一刻的状态。这是电商的标准做法。

### 8. Session 怎么管理

`get_db` 依赖：请求进入创建 Session，`yield` 给路由，`finally` 里 `close()`。engine 配了 `pool_size=10`、`pool_recycle=3600`。

**一个例外**：SSE 长连接**不用**请求作用域的 Session——流式响应会长时间持有连接，客户端断连时依赖注入还可能并发关闭它。所以 `ai_chat.py` 通过 `get_session_factory` 依赖拿到 Session 工厂，在生成器内部自建自关。用工厂（而不是直接 `SessionLocal()`）是为了测试能覆盖依赖注入。

### 9. 商品列表的搜索/筛选/排序/分页

- 搜索：`ilike` 匹配 `products.name`、`description` 和 `categories.name`（`outerjoin` 分类表），ORM 参数化天然防注入；
- 分类：支持二级，先查子分类 id 再 `IN`；
- 排序：`sort_by` 走**白名单**（created_at/price/sales/stock），防止任意字段排序；
- 分页：`offset/limit`，`page_size` 用 `Query(ge=1, le=100)` 限制上限；
- 关联加载：`selectinload(Product.skus)` 与 `selectinload(Product.category)`，避免 N+1（category 这处原来是漏的，审计时补上的）。

### 10. 图片上传

仅管理员可调 `POST /admin/upload`：校验扩展名白名单（jpg/jpeg/png/gif/webp）+ 大小 ≤2MB，文件名用 `uuid4().hex` 重命名（防路径穿越与覆盖），存本地 `static/products`，返回 URL 落库。

不足：只校验扩展名、不校验文件魔数；生产应换成 OSS/COS + CDN。

---

## 三、认证与安全

### 11. JWT 流程

1. 登录成功后用 `python-jose` 签发 HS256 token，payload 是 `sub=user_id` + `exp`（默认 1440 分钟）；
2. 前端存 localStorage，axios 请求拦截器自动加 `Authorization: Bearer`；
3. 后端 `get_current_user`：`HTTPBearer` 取 token → 验签名/过期 → 查库确认用户存在且 `is_active`；
4. 401 时前端拦截器清 token 并跳登录页。

### 12. 密码怎么存

`bcrypt.hashpw + gensalt`，库里只存哈希，登录用 `checkpw` 校验。

两个坑：① bcrypt 只取前 72 字节，代码里显式 `encode()[:72]` 截断；② `passlib[bcrypt]` 与新版 bcrypt 库不兼容会直接报错，最后弃用 passlib、直接调用 bcrypt。

### 13. RBAC 怎么做的

`User.role` 枚举 `user/admin`。依赖链 `get_current_user`（认证）→ `get_current_admin`（校验 `role == ADMIN`，否则 403）。管理端路由统一挂 `Depends(get_current_admin)`。

前端守卫只是体验层，**真正的权限校验在服务端**——测试里有专门用例断言普通用户访问 `/api/v1/admin/**` 返回 403。

### 14. AI 客服为什么允许不登录（以及怎么防止越权）

用 `get_optional_user`：`HTTPBearer(auto_error=False)`，有合法 token 就解析出用户，没有就 `None`。

**会话归属规则**（`chat_service.get_accessible_session`）：

- 已绑定用户的会话：只有本人可访问，否则 **403**；
- 匿名会话（`user_id` 为空）：AI 客服允许未登录使用，因此**仅靠 UUID 不可猜测性保护**；登录用户首次访问会把会话「认领」到自己名下，这样先匿名聊天再登录不会丢历史；
- 会话不存在返回 **404**。

> 这是一个真实修过的漏洞：原实现把 `get_optional_user` 取到的用户直接丢掉（参数名甚至是 `_`），也不校验归属，导致**任何拿到 session_id 的人不带 token 就能读、能删别人的会话**。现在 `test_security.py` 里有 6 条针对会话归属的用例（跨用户读写 403、本人可读、不存在 404、匿名可读、登录认领）。

### 15. 做了哪些安全措施？还有哪些不足？

**已有**：JWT + bcrypt；RBAC 且测试覆盖 403；ORM 参数化防注入；Vue 默认转义 + 全项目零 `v-html`（无 XSS）；CORS 白名单；上传类型/大小校验 + uuid 重命名；会话归属校验；订单/地址/购物车均按 `user_id` 过滤（水平越权防护）。

**不足（主动讲，显得清楚）**：

- token 存 localStorage，有 XSS 窃取风险 → 应改 httpOnly Cookie + refresh token；
- 无接口限流（登录/下单/聊天）；
- 无 HTTPS（compose 里是 HTTP）；
- 匿名会话只靠 UUID 保密性，严格做法是签发受限的访客 token；
- 上传只校验扩展名，未校验魔数；图片存本地盘。

---

## 四、电商核心业务

### 16. 购物车怎么设计

`cart_items(user_id, product_id, sku_id, quantity)`，唯一约束 `(user_id, sku_id)`，同用户同 SKU 累加数量。

- 加购：商品必须上架，且**校验累加之后的总量**不超库存；
- 金额与数量只统计上架商品，`total_count` 与返回的 `items` 保持一致；
- 合计用 `Decimal` 计算，不用 float。

> 修过的 bug：原来只校验「本次加购数量」，stock=3 时加 2 再加 2 会得到 4 件；`total_count` 也把已下架的行算进去了。

### 17. 下单流程完整说一遍

1. 校验收货地址属于当前用户（否则 404）；
2. 购物车非空（否则 400）；
3. 逐项校验商品上架，并**原子扣减** SKU 与商品聚合库存（见 Q20），任一失败抛「库存不足」；
4. 生成订单号：`年月日 + uuid4().hex[:12].upper()`，`order_no` 唯一索引兜底；
5. 保存地址快照（JSON）；
6. 建 `Order`（`pending_pay`），`flush` 拿 id；
7. 建 `OrderItem`，写入商品名/图/规格/单价快照；
8. 清空购物车；
9. **一次性 `commit`**。

> **注意两件事**，别答错：
> - **销量在「支付成功」时才累加**，不是下单时；
> - 第 8 步的 `clear_cart` 必须 `commit=False`。原实现在 `create_order` 事务中途 `commit`，等于把「扣库存 + 建订单」提前落库了，之后任何异常 `rollback()` 都回滚不掉。这是个真实的事务原子性 bug。

### 18. 订单号为什么不用自增 id

自增 id 会暴露业务量、不可重排、跨表引用不直观。用「日期 + 随机 hex」，可读、可按时间排序、方便对账，唯一索引兜底。

### 19. 订单状态机

```
pending_pay --支付--> paid --发货--> shipped --确认收货--> completed
     |                  |             |
     +--取消(回补库存)    +-------------+--申请退款--> refunding --审核通过--> refunded
                                                          |
                                                    审核驳回 --> 回到原状态
```

- 用户只能取消 `pending_pay` 的订单，取消会回补库存；
- 管理员改状态**校验流转合法性**：`_ADMIN_ALLOWED_TRANSITIONS` 白名单（`pending_pay → {paid, cancelled}`、`paid → {shipped}`、`shipped → {completed}`），非法流转返回 400；
- 支付/确认收货/退款审核都在 `refunding` 态上做条件更新。

### 20. 怎么防库存超卖（重点题）

**没有用 check-then-act**，而是**一条带条件的原子 UPDATE**：

```sql
UPDATE product_skus SET stock = stock - :qty
 WHERE id = :sku_id AND stock >= :qty;
```

- 判断依据是 `rowcount`，为 0 说明库存不足，抛 400，整个事务回滚；
- SKU 与商品聚合库存都要扣，两者任一失败即回滚；
- 这样不需要额外加锁，也不需要重试循环——InnoDB 的行锁保证了 `stock >= qty` 的判断与扣减在同一语句里原子完成；
- 有**多线程并发下单**的 pytest 用例验证（`ThreadPoolExecutor(max_workers=8)`，每线程独立 Session）。

**同一个思路用在了订单状态流转上**（乐观并发控制）：

```sql
UPDATE orders SET status = 'paid', paid_at = NOW()
 WHERE id = :id AND status = 'pending_pay';
```

靠 `rowcount` 判断是否抢到。否则并发两次支付可能都读到 `pending_pay`，**销量被累加两次**；后台 30 秒轮询的自动关单任务也可能把刚支付成功的订单改成 `cancelled`。

**如果继续深入，可以补充**：悲观锁（`SELECT ... FOR UPDATE`，吞吐低）、Redis 原子预扣（秒杀场景，异步落库）。当前量级用条件更新最合适。

### 21. 金额计算注意什么

- DB 用 `DECIMAL(10,2)`，不丢精度；
- 订单总额**由后端按库中价格计算**，绝不信任前端传价；
- 购物车合计用 `Decimal`（不是 float + round）；
- 快照价存 DECIMAL，历史订单金额永远可还原。

### 22. 订单超时自动关单怎么做

`app/core/tasks.py` 在 FastAPI `lifespan` 启动一个 asyncio 后台任务，每 30 秒把 `pending_pay` 且创建超过 `ORDER_EXPIRE_MINUTES`（默认 30 分钟）的订单关掉并回补库存。

实现上是**逐单条件 UPDATE**，和用户支付抢同一行——抢不到就跳过（说明期间已被支付或取消）。这样不会出现「已支付却被关单」。测试覆盖了：能正常关单并回补库存、重复执行不会重复回补、已支付订单不受影响。

> 不足：多副本部署时每个实例都会跑这个循环；生产应改成分布式锁或独立的定时任务服务。

---

## 五、AI 智能客服（RAG）

### 23. 什么是 RAG，项目里怎么落地

RAG = 检索增强生成：先检索相关知识，再让模型基于检索结果回答，缓解「知识过期」和「幻觉」。

**离线**：管理员在后台维护知识文档 → `RecursiveCharacterTextSplitter` 切片（chunk 500 / overlap 50）→ 本地 BGE 向量化 → 存入 ChromaDB。文档增删改只重建**该文档**的向量。

**在线**：用户提问 → （多轮时）先做 Query 改写 → 检索 top-3 → 距离 > 0.7 的丢弃 → 拼进 System Prompt → DeepSeek 流式生成 → SSE 推给前端。无知识命中时退化为商品库检索并推送商品卡片。

### 24. 为什么选 ChromaDB

| 方案 | 部署 | 规模 | 结论 |
|---|---|---|---|
| ChromaDB | pip 安装、零配置、本地持久化 | 万级以内 | 本项目选择 |
| Milvus | 需 Docker/集群 | 亿级 | 过重 |
| FAISS | 库而非服务 | 灵活 | 持久化/管理弱 |
| Pinecone | 云托管 | 弹性 | 收费 |

按数据量和部署成本选最轻的，代码里封装在 `vectorstore` 模块，可替换。

### 25. Embedding 为什么本地部署 BGE

- DeepSeek 官方 API 只提供对话生成，不提供 embeddings；
- `BAAI/bge-small-zh-v1.5` 中文检索效果好、约 100MB、免费、无外网依赖（推理时）；
- 通过 ModelScope 下载（国内可用，HuggingFace 被墙）；
- `normalize_embeddings=True` + CPU 推理，Demo 场景够用。

### 26. chunk_size / overlap / separators 怎么定的

- 500 字符：接近一段中文说明的合适粒度，太小丢上下文，太大降低检索精度；
- overlap 50：防止关键信息恰好被切在两段之间（比如一句退换货规则）；
- separators 按 `\n\n → \n → 。 → ， → 空格 → ""` 优先级，尽量保持语义完整。

### 27. 怎么抑制幻觉

三重防线：① System Prompt 明确「只依据知识库回答，不得编造，没有就说无法回答并引导人工」；② 检索结果按余弦距离阈值过滤，没有相关上下文就不硬答；③ 无命中时改走商品库兜底 + 兜底话术。

### 28. 为什么用 SSE 而不是 WebSocket

场景是单向流：用户发一条 → AI 逐字返回，HTTP 流就够。SSE 基于普通 HTTP，`StreamingResponse` 即可实现，浏览器原生支持。

WebSocket 需要协议升级、连接池、心跳保活、断线重连，复杂度不划算。另外 Nginx 侧要关掉缓冲（`proxy_buffering off` + 响应头 `X-Accel-Buffering: no`），否则流式会失效。

### 29. 前端怎么消费 SSE

用 `fetch` 而不是 `EventSource`（因为要 POST，且要带 `Authorization` 头，EventSource 两者都不支持）：

- `fetch` POST → `response.body.getReader()`；
- `TextDecoder({ stream: true })` 按字节流解码，并用 residual buffer 处理跨 chunk 截断的**多字节中文**——这是最容易出乱码的地方；
- 按行分帧识别 `data:` 前缀，处理 `[DONE]` / `[ERROR]` 以及自定义的 `products` 事件（商品卡片）；
- 先插入空的 assistant 消息占位，逐字 append，实现打字机效果。

### 30. 知识库更新后向量索引怎么同步

**增量**，不是全量重建：文档增删改后调 `indexer.sync_knowledge_doc` → 先 `collection.delete(where={"id": doc_id})` 删掉该文档的旧切片，再用 ids `{doc_id}-{i}` 写入新切片。批量导入 `.md/.txt` 时逐篇走同一路径。

> 早期版本是 `shutil.rmtree` 整个 Chroma 目录后全量重建，文档一多就很慢。

### 31. 多轮对话怎么实现

会话历史存 `chat_sessions` / `chat_messages`（`session_id` 由前端生成，未登录也能持久化）。

每轮：取最近 6 条历史 → 若历史非空，先用 LLM 做一次 **Query 改写**（把「它多少钱」改写成「iPhone 15 Pro Max 多少钱」）→ 用改写后的 query 检索 → 生成。回答完成后把 assistant 消息也落库。

注意点：历史要截断（每条约 300 字、最多 6 条）以控制 token；生产上 memory 应按用户隔离并设成本上限。

### 32. RAG 效果怎么量化（**这是最能加分的一题**）

有 `tests/test_rag_quality.py`：加载**真实** `bge-small-zh-v1.5`，对 10 篇知识文档建索引，跑 20 条评测用例，按**生产同款参数**（余弦距离 ≤ 0.7、top-3）算召回。

**自建 20 条评测集，其中一半是口语化改写、与原文几乎没有字面重叠**（例如「在没有手机信号的地方还能打电话吗」→ 卫星通话文档）。只用关键词重合就能全中的评测集是没有意义的。

实测结果：

| 指标 | 数值 |
|---|---|
| recall@1 | **90%** |
| recall@3（生产取 top-3） | **95%** |
| recall@10 | **100%** |

**一个真实的负向结论**（面试时讲这个比讲成功案例更可信）：

我以为 `bge-*-zh` 需要按 BGE v1 的用法给 query 加指令前缀「为这个句子生成表示以用于检索相关文章：」，加完做 A/B 发现——**命中率不变，但平均余弦距离从 0.357 劣化到 0.401**。因为 **v1.5 已经不需要该前缀**（那是 v1 的要求），加了反而把 query 推出文档语义空间。于是**回滚了这个改动**，并把结论写进 `vectorstore._embed` 的注释。

另外测出：在 10 篇文档的小语料上，只有 8.5% 的「query-文档」距离超过 0.7，也就是说**阈值在这个规模下几乎不过滤任何东西**——它是为大规模语料准备的护栏，不是小语料上的召回杠杆。

> 评测集规模（20 条 / 10 篇）决定这个数字只能当**冒烟测试**看，不能当基准榜单。想更有说服力就把知识库和用例都扩到几百条。

### 33. LangChain 兼容踩了什么坑

装 `langchain-huggingface` 时依赖解析把 `langchain-core` 拉到了 1.x，导致 `langchain.prompts`、`langchain.text_splitter` 等导入路径全部失效。最后把 `langchain / core / text-splitters / chroma / openai / huggingface` 全部 pin 到 0.3.x 兼容组合。

**教训**：LLM 生态迭代极快，必须锁版本并用 requirements.txt 固化。

另外一个坑：`langchain-chroma` 0.2.2 要求 `chromadb < 0.7`，与 1.x 的预编译 wheel 冲突，所以**放弃 langchain-chroma，直接调用 Chroma 原生客户端**，上层 RAG 代码不受影响。

---

## 六、前端

### 34. 状态管理怎么用，为什么选 Pinia

- `auth`：用户信息 + 登录/注册/登出，localStorage 持久化；
- `cart`：购物车数量角标、拉取、加购；
- `chat`：AI 消息列表、打开状态、流式文本拼接。

选 Pinia：Vue3 官方推荐、支持 setup 写法、比 Vuex 代码量少。

### 35. axios 拦截器做了什么

- 请求拦截器：从 localStorage 取 token（商城 `token` / 后台 `admin_token`），自动加 `Authorization: Bearer`；
- 响应拦截器：直接返回 `data`（少一层解包）、统一 `ElMessage` 错误提示、401 清 token 跳登录页。

### 36. 商城前台和管理后台怎么区分

两个独立 Vite 工程（5173 / 5174），各有自己的 `main`、router、api client、store。后台 vite 配 `base: '/admin/'`，生产构建由同一个 Nginx 托管在 `/admin/` 子路径。

后台路由守卫：全局 `beforeEach` 检查 `admin_token`，再调 `/auth/me` 确认角色是 admin，否则跳登录。**前端守卫只是体验层**，真正的权限在后端 `get_current_admin`。

商城前台现在也改成了全局守卫：路由上标 `meta.requiresAuth`，`beforeEach` 统一拦截并带上
`redirect` 参数，登录后回到原本要去的页面。改成统一守卫之前是每个页面各写一遍
`onMounted` 判断，重复不说，`/user/profile` 和 `/user/addresses` **两个页面压根漏了**，
未登录也能打开然后接口报 401。

> 顺带一个真实的调试案例：审计报告说「组件里直接给 Pinia setup store 的 ref 赋值
> （`cartStore.count = x`）是破坏响应式的写法，必须走 store action」。我没有直接改，
> 而是写了个小脚本用项目里已装的 pinia + vue 实测了一遍：赋值生效、`computed` 重算、
> `watch` 触发。**结论是这个说法不成立，那行代码是对的，于是一个字都没动。**
> 差一点就把正确的代码「修」坏了——这也是为什么我不想只凭静态阅读下结论。

### 37. Vue3 用了哪些特性

组合式 API（`ref` / `computed` / `watch`）、`<script setup>`、路由级懒加载（`import()`）、Pinia setup store；后台大量使用 Element Plus 的表格/表单/弹窗/消息组件。

---

## 七、测试、CI 与部署

### 38. 测试怎么做的（51 个用例）

| 文件 | 覆盖 |
|---|---|
| `test_auth.py` | 注册/登录/JWT/重复注册/错误密码/无 token |
| `test_products_cart_orders.py` | 商品列表详情、购物车库存校验、SKU 归属校验、分页上限、下单→支付→发货→确认收货→退款→审核（含驳回）全流程 |
| `test_stock.py` | 顺序超卖拦截 + **多线程并发下单**不超卖（SQLite） |
| `test_security.py` | 地址 404、跨用户读/删会话 403、本人可读、匿名会话与认领、**禁用账号失效**、**用户名枚举**、**订单水平越权**、管理端 403/401/200 |
| `test_regressions.py` | 15 个回归用例，每个对应一个真实修过的缺陷（含订单列表 N+1） |
| `test_config.py` | 启动自检：默认 JWT 密钥在 production 下拒绝启动 |
| `test_ai.py` | 知识增量索引与检索、评测接口统计 |
| `test_rag_quality.py` | **真实 BGE 模型**下的召回率（无模型时自动 skip） |
| `test_mysql_integration.py` | **真实 MySQL/InnoDB**：外键、并发防超卖、并发支付幂等（连不上时自动 skip） |

工程要点：默认 47 个用例完全自包含——每个用例一个独立 SQLite 文件、覆盖 `get_db` 依赖、
假 Embedding（确定性哈希向量），**不需要 MySQL 也不需要联网**，所以 CI 跑得很快。
需要真实数据库/模型的用例用 marker 标注并自动 skip，不会让 CI 变红。

### 38b. 为什么还要单独写一套 MySQL 测试（**很值钱的一题**）

因为 SQLite **验证不了生产真正依赖的东西**：SQLite 会把写操作整体串行化，
永远不会真正并发地去抢同一行；而生产用 MySQL/InnoDB，靠的是行锁 +
`UPDATE ... WHERE stock >= ?` 的 `rowcount`。在 SQLite 上这条用例通过，
**并不能证明在 InnoDB 上也没问题**。

`tests/test_mysql_integration.py` 在 MySQL 8.0.43 上实测：

| 场景 | 结果 |
|---|---|
| 8 线程并发抢 3 件库存 | 恰好 3 单成功，SKU 与商品聚合库存同时归零 |
| 同一订单 5 次并发支付 | 恰好 1 次成功，销量只累加 1 |
| 删除已被下单的商品 | 抛 `IntegrityError`——证明服务层拦截是必要的；SQLite 默认不校验外键，这条约束在 SQLite 上**根本看不出来** |

关键设计：**失败的线程只接受「库存不足 / 状态不允许」这类业务错误**，其他异常一律抛出。
否则某个代码 bug 让 5 个线程报错，`成功数 == 3` 依然会通过，测试就成了假的通过
——原来那版 SQLite 用例把所有异常都吞掉了。

写这套测试时踩到一个真实的 MySQL 坑，很值得讲：会话在起线程前已经读过数据，
而 MySQL 默认隔离级别 **REPEATABLE READ** 会把只读事务的一致性快照固定在那一刻，
于是并发支付明明成功了，测试里再查却仍是 `pending_pay`。必须先 `rollback()`
结束该事务再断言。**SQLite 上不会遇到，原来那条断言在 SQLite 版里是「碰巧」成立的。**

### 39. CI 做了什么

GitHub Actions，四个 job：

- **backend**：`ruff check` → `pytest --cov=app --cov-fail-under=70`（覆盖率是门槛，不是装饰）
  → `python -c "from app.main import app"` 冒烟（确认应用能正常导入）；
- **mysql-integration**：带 MySQL 8 service 容器跑 `pytest -m mysql`，把「8 线程抢 3 件库存
  恰好成交 3 单」「5 次并发支付恰好成功 1 次」变成每次提交都能复现的证据。因为这套用例
  连不上库时会 **skip（而不是失败）**，所以这一步显式断言日志里不能出现 `skipped`
  ——否则 host/口令配错时会得到一个绿色的假通过；
- **rag-quality**：**手动触发**（`workflow_dispatch`）才跑 `pytest -m rag_quality`。
  它要下载约 100MB 的 BGE 模型，放进每次 push 的流水线会又慢又容易因网络抖动变红；
- **frontend**：`frontend` / `admin` 矩阵，`npm ci` + `npm run lint` + `vite build`。

因为默认那 47 个用例跑在 SQLite + 假向量上，backend job **不需要 MySQL、也不下载
100MB 模型**，所以跑得很快；需要真实数据库/模型的用例各自由上面两个独立 job 负责。

ruff 刻意只开 `F`（如 F821 undefined-name）和 `E9`：**只拦「一定是 bug」的规则、不引风格
偏好**，避免 CI 一上来就红。F821 恰好就是本项目踩过的那个坑——`api/users.py` 用了
`status.HTTP_404_NOT_FOUND` 却没 import `status`，导致改/删不存在的地址直接 500。
这个规则集也一次性清掉了 9 个真实的死导入。

### 40. 怎么部署

`docker compose up -d --build` 起三个服务：

- **mysql**（8.0，healthcheck，口令通过 `MYSQL_PWD` 传，不出现在 `ps` 里）；
- **backend**：entrypoint 带**超时上限**地等待 MySQL 就绪（原先是无上限循环，数据库起不来
  容器就永久挂住）→ `alembic upgrade head` → `python -m app.core.seed`（幂等）→ uvicorn；
  镜像**非 root 运行**并带 HEALTHCHECK；
- **web**：多阶段构建（两个 node 阶段 `npm ci` + build）→ nginx 托管静态产物并反代
  `/api`、`/static`，`web` 会等 backend healthy 才启动。

Nginx 关键配置：`/api/` 反代 `proxy_buffering off` + `proxy_cache off`（否则 SSE 被缓冲）、
`client_max_body_size 8m`（默认 1m 会让 2MB 的图片上传直接 413）、gzip、安全响应头
（CSP 逐条注明放开条件）、带 hash 的 `/assets/` 长缓存。

### 41. 上线前还差什么（主动列出，显示清楚边界）

**安全**：HTTPS（HSTS 已在 nginx 注释好，等 TLS 终结后打开）、接口限流、refresh token、
上传魔数校验；JWT 仍在 localStorage；backend 的 8000 端口直连宿主机，所以
`--forwarded-allow-ips='*'` 是有折扣的信任，生产要收紧。

**数据库**：`alembic downgrade` 目前只有索引迁移是真实可用的，V2 那个大迁移仍是 `pass`。

**稳定性**：多副本时超时关单任务会在每个副本各跑一份，需要分布式锁；
无结构化日志/监控告警。

**前端**：无 TypeScript、无单元测试；各页面里还留着早期手写的 `onMounted` 登录判断
（已被全局守卫取代，属冗余）。

---

## 八、难点与复盘

### 42. 最大的难点

挑最真实的几个讲：

1. **RAG 链路跑通**：Embedding 模型下载被墙、LangChain 依赖升级破坏兼容 → ModelScope 下载 + 全部锁定 0.3.x；`langchain-chroma` 与 chromadb 1.x 冲突 → 直接调 Chroma 原生客户端。
2. **SSE 中文流式渲染**：多字节字符在流边界被截断成乱码 → `TextDecoder({stream:true})` + 残留 buffer + 按行缓冲。
3. **并发正确性**：从「先查库存再扣减」的 check-then-act，改成条件 UPDATE + rowcount 判断，并把同一思路用到订单状态流转上；在 SQLite 和**真实 InnoDB** 上都做了并发验证。
4. **「查过再改」的价值**：两次都是先动手量，结论和「看起来应该这样」相反——BGE 指令前缀加上去反而更差（回滚）；审计说一堆外键列缺索引，实测 InnoDB 早就自动建好了（不重复造索引）。差点根据静态阅读把正确的代码改坏。

### 43. 项目有哪些不足，重来会怎么改

- 前端没有 TypeScript、没有单元测试；页面里还留着已被全局守卫取代的重复鉴权判断；
- V2 大迁移的 `downgrade()` 还是空实现；
- JWT 存 localStorage、无限流、无 HTTPS；
- 多副本时定时关单任务会重复执行；
- 匿名会话只靠 UUID 保密性。

**重来**：先定接口契约与迁移策略，再写业务；把 AI 客服拆成独立服务与交易模块解耦；测试从第一天就上 CI；**凡是"性能/效果优化"先用数据验证再合入**。

### 44. 亮点是什么

- **完整闭环**：从前端交互、交易链路到 AI 客服全部打通，不是玩具 Demo；
- **有可量化的 AI 效果**：自建评测集，recall@1 90% / recall@3 95%，并且做过 A/B 得出「BGE 指令前缀对 v1.5 有害」的负向结论并回滚；
- **并发正确性经过真实数据库验证**：8 线程抢 3 件恰好成交 3 单、5 次并发支付恰好成功 1 次，失败原因被严格限定为业务错误；
- **工程化**：分层架构、依赖注入、Alembic 幂等迁移（含可用的 downgrade）、多阶段非 root 镜像、Compose + Nginx、51 个测试（覆盖率 72%）、CI；
- **清楚边界**：知道上线还差什么、瓶颈在哪、怎么扩展。

### 45. 如果流量上来先瓶颈在哪

- **MySQL**：商品热点加 Redis 缓存（现在每次都查库）；下单写压力用消息队列削峰；
- **向量检索**：ChromaDB 单机容量有限 → Milvus 或副本；
- **LLM 调用**：相似问题结果缓存、限流、多 Key 轮询降成本；
- **后端**：FastAPI 无状态，可水平扩容 + Nginx 负载均衡（注意后台任务要改成分布式）；
- **图片**：本地盘 → OSS/COS + CDN。
