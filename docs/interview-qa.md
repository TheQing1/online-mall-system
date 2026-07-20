# AI 智能客服商城 — 面试问答

---

## 一、RAG 原理与架构

### Q1: 什么是 RAG？你这个项目里是怎么实现的？

**RAG**（Retrieval-Augmented Generation，检索增强生成）解决了大模型的两个核心问题：**知识时效性**（模型训练数据有截止日期）和**幻觉**（模型会编造不存在的信息）。

我的实现流程：

```
用户提问 → Embedding 向量化 → ChromaDB 相似度检索 (Top-K=3)
→ 构建 Prompt（系统指令 + 检索到的知识 + 用户问题）
→ DeepSeek 流式生成 → SSE 推送前端
```

具体来说：
1. **离线阶段：** 管理员在后台编写知识库文档（退换货政策、产品参数等），保存时自动用 `RecursiveCharacterTextSplitter`（chunk_size=500, overlap=50）切分，通过 BGE 中文模型向量化后存入 ChromaDB
2. **在线阶段：** 用户提问 → 同一个 Embedding 模型向量化 → ChromaDB 做语义相似度检索（不是关键词匹配，是语义匹配）→ 检索到的文档片段作为上下文注入 LLM 的 System Prompt → LLM 基于给定知识回答

**关键：** LLM 只根据检索到的知识回答，知识库没有的就明确告知用户无法回答，有效防止幻觉。

---

### Q2: 为什么用 ChromaDB？和其他向量数据库对比过吗？

| | ChromaDB | Milvus | FAISS | Pinecone |
|------|----------|--------|-------|----------|
| 部署 | Python pip 安装，零配置 | 需 Docker/SaaS | Python 库，内存/磁盘 | 云服务 |
| 规模 | 小中型（万级） | 大规模（亿级） | 灵活 | 弹性扩展 |
| 学习成本 | 低 | 高 | 中 | 低 |

选 ChromaDB 的理由：项目是 Demo 级别，知识库几十篇文档，不需要分布式。`pip install chromadb` 就可以跑，和 LangChain 原生集成，持久化到本地磁盘。

---

### Q3: 为什么选择 SSE 而不是 WebSocket？

AI 客服场景是**单向流**：用户发一条消息 → AI 逐字返回。SSE 完全够用：

- **SSE：** 基于 HTTP，浏览器原生支持自动重连，FastAPI `StreamingResponse` 一行代码搞定
- **WebSocket：** 需要升级协议、管理连接池、实现心跳保活，更重

就像下载文件用 HTTP 不用 WebSocket——单向数据流不需要双向通信。

---

### Q4: 文档切分的 chunk_size 和 overlap 怎么定的？

- **chunk_size=500：** 基于中文语义。太小（如200）会丢失上下文，太大（如1000）检索精度下降。500 约等于一段中文说明文字的长度
- **overlap=50：** 防止关键信息被切在两段中间。比如 "自收到商品之日起7日内可申请无理由退货" 如果被切在两段，检索可能匹配不到完整信息

分隔符设为 `["\n\n", "\n", "。", "，", " ", ""]`，优先按自然段落和句子切分，保持语义完整性。

---

### Q5: 怎么保证 AI 不胡说八道？

三重防线：
1. **Prompt 约束：** System Prompt 明确指令 "仅根据上述知识库内容回答问题，不要编造信息"
2. **相似度阈值过滤：** 检索结果的 L2 距离 > 0.7 的结果直接丢弃
3. **兜底话术：** 没有相关文档时 Prompt 的上下文为空，LLM 按照指令回复 "建议联系人工客服"

---

## 二、Embedding 模型

### Q6: 为什么不用 DeepSeek 的 Embedding API，而是本地部署？

DeepSeek API 提供 Chat Completions（对话生成），但**不提供 Embeddings 服务**。我最初尝试了 `text-embedding-3-small`（那是 OpenAI 的模型名），DeepSeek 返回 404。

换成本地部署 `BAAI/bge-small-zh-v1.5`：
- **免费**，无需 API Key
- **中文优化**，语义理解比通用多语言模型准
- HuggingFace 被墙，改用 ModelScope（阿里云平台）下载

---

### Q7: BGE 模型和其他 Embedding 模型的区别？

BGE（BAAI General Embedding）是智源研究院开源的 Embedding 模型，专门优化了检索任务的语义表示。`bge-small-zh-v1.5` 是中文小版本（约 100MB），在中文语义相似度（STS）和检索评测上超过同级别的 `text2vec` 和 `m3e`。

---

## 三、系统架构

### Q8: 整个系统的架构是怎样的？

```
前端商城 :5173 (Vue3)   管理后台 :5174 (Vue3)
         ↘              ↙
      FastAPI :8000 (REST + SSE)
         ↙              ↘
    MySQL (业务数据)   ChromaDB (向量)
                           ↓
                      DeepSeek API (对话)
                    BGE 本地模型 (Embedding)
```

- 前端两个独立 Vite 入口，通过 Vite proxy 转发 `/api` 到后端
- 后端三层架构：API 路由 → Service 业务逻辑 → Model 数据层
- 认证：JWT Bearer Token，前后台使用独立 Token key（`token` / `admin_token`）
- AI 客服：支持可选登录（`get_optional_user`），未登录也能用

---

### Q9: 订单系统怎么设计的？支付怎么处理的？

订单创建流程：
1. 验证收货地址 → 2. 获取购物车商品 → 3. 校验库存和上架状态 → 4. 生成订单号（日期+12位随机hex）→ 5. 快照地址（JSON存储，下单后地址修改不影响订单）→ 6. 创建订单+订单项（快照商品名/价格/图片）→ 7. 扣减库存+增加销量 → 8. 清空购物车

**支付：** 当前是模拟支付——下单后自动标记为 `paid`。设计的订单状态流转为 `pending_pay → paid → shipped → completed`，取消 ∈ `{pending_pay}` 且恢复库存。接入真实支付（微信/支付宝）只需在 `paid` 之前插入支付回调处理。

---

### Q10: 库存超卖怎么处理？

当前做了基本防护：下单时检查 `product.stock >= cart_item.quantity`。但高并发场景下存在 **check-then-act** 竞态条件。

解决方案（已规划）：
1. **悲观锁：** `SELECT ... FOR UPDATE` 锁定行，确保同一商品同一时刻仅一个事务修改库存
2. **乐观锁：** 在 `Product` 表加 `version` 字段，更新时 `WHERE version = old_version`，失败则重试
3. **Redis 预扣库存：** 秒杀场景常用，Redis 原子 decr，异步落库

---

## 四、难点与解决方案

### Q11: 做这个项目遇到的最大难点？

**1. Pydantic 序列化 datetime：** `ProductOut.created_at` 声明为 `str`，但 SQLAlchemy 返回 `datetime` 对象。最初用 `field_serializer`，发现它只在 JSON 序列化阶段生效，from_attributes 验证阶段不走。最终改用 `field_validator(mode="before")` 在验证前转换。

**2. LangChain 版本兼容：** 后来安装 `langchain-huggingface` 时自动升级了 `langchain-core` 到 1.x，导致大量 API 变动（`langchain.prompts` → `langchain_core.prompts`，`langchain.text_splitter` → `langchain_text_splitters`）。最终将全部 LangChain 组件 pin 到 0.3.x 兼容版本解决。

**3. HuggingFace 被墙：** 本地 Embedding 模型无法从 HuggingFace 下载。尝试了 `hf-mirror.com` 镜像无效。最终改用阿里云 ModelScope SDK 下载，全程国内网络可用。

**4. passlib 与 bcrypt 版本不兼容：** `passlib[bcrypt]` 调用新版 bcrypt 时报错。直接用 `bcrypt` 库替代 passlib，`hashpw` / `checkpw` 更简洁可靠。

---

### Q12: 知识库更新后，AI 怎么知道新内容？

管理后台保存知识库文档时，触发 `_sync_knowledge_index()`：
1. 查询 MySQL 中所有知识库文档
2. `RecursiveCharacterTextSplitter` 重新切分
3. 清空旧 ChromaDB 索引，全量重建

当前是全量重建策略（适合文档量小）。生产环境可优化为增量更新（只更新变动的文档对应的向量）。

---

## 五、拓展问题

### Q13: 如果要上线，还需要做什么？

- **数据库：** 加索引（product.name 全文索引、order.user_id+status 联合索引）、Redis 缓存热点商品
- **安全：** JWT refresh token、接口限流、SQL 注入已由 ORM 防护、XSS 由 Vue 默认转义防护
- **AI：** 多轮对话记忆（LangChain `ConversationBufferMemory`）、向量索引增量更新
- **部署：** Docker Compose（FastAPI + MySQL + ChromaDB）、Nginx 反代、CDN 静态资源

### Q14: 多轮对话怎么做？

当前是单轮（每次提问独立检索+生成）。多轮对话需要：

```python
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain

memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
qa = ConversationalRetrievalChain.from_llm(
    llm=get_llm(),
    retriever=get_vectorstore().as_retriever(),
    memory=memory,
)
```

关键在于 `chat_history` 会随每轮对话追加，LLM 能理解上下文（如 "它多少钱" → 知道 "它" 指上一轮提到的商品）。
