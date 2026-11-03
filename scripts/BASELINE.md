# 已知依赖漏洞与处理口径

> 这份文档存在的意义：**说清楚「哪些洞我们查过了、为什么不升、什么时候必须升」**。
> 面试被问到时能直接翻这一页，比含糊说「没做过安全扫描」强得多。

## 现状

用 `pip-audit -r backend/requirements.txt` 扫描的结果：
**23 条漏洞，分布在 7 个包**（不含 pip / setuptools 这类工具链自身的条目）。

> 建档时是 **39 条 / 11 个包**，经历两次依赖治理后降到现在的数字：
> - `python-jose` → PyJWT 迁移，消掉 5 条（见 D 组）；
> - LangChain 生态整组升级（0.3.13 → 0.3.30，含 `langchain-huggingface`
>   0.1.2 → 0.3.1），再消掉 6 条并移除 2 个包（见 E 组）。

基线文件：`scripts/security-baseline.json`（由脚本自动生成，请勿手改）。

```bash
bash scripts/security-audit.sh            # 检查是否有新增漏洞
bash scripts/security-audit.sh --update   # 重新生成基线（需人工 review）
```

扫描策略是**基线模式**而不是全量卡死，理由：一条 23 处红叉、且长期没人处理的检查，
唯一的效果是让大家习惯性忽略它。基线模式能保证「新引入一个带洞的依赖」立刻被拦住，
同时让存量问题保持可见。

## 分组与处理口径

### A. 受框架版本约束，暂时无法单独升级（**最主要的一类**）

| 包 | 当前 | 修复版本 | 为什么不能升 |
|---|---|---|---|
| `starlette` | 0.38.6 | 0.40 / 0.47 / 1.x | **FastAPI 0.115 要求 `starlette>=0.37.2,<0.39`** |
| `python-multipart` | 0.0.9 | 0.0.18 ~ 0.0.31 | 与 starlette 的表单解析配套，需同步升级 |

这是本项目**唯一一处「知道有洞但不能升」**的地方，且是框架强约束，不是偷懒。

解除条件：单独排期把 FastAPI 从 0.115 升到大版本（0.162+），同步升 starlette，
然后**完整重跑 138 个后端用例 + 18 个 e2e**。这牵涉 Router、`on_startup`、
中间件行为等破坏性变更，不能顺手做。

风险说明：这些 CVE 的利用前提多为「特定配置 + 可访问的特定入口」。本项目是
单机 demo 形态、无真实用户数据，实际暴露面有限——但**这不等于可以永远不升**。

### B. AI 依赖链（已整组升级，仅剩少量残留）

`langchain`(1) / `langchain-core`(2) / `langchain-openai`(1) / `langchain-text-splitters`(1)
——共 5 条，且都是**更高 major 才能修**的那种（需要 langchain 1.x）。
`langsmith` 与 `langchain-huggingface` 已随整组升级清零，见 E 组。

剩下这 5 条的处理口径：修它们需要跨到 langchain 1.x，而 1.x 的 API 与 0.3.x
差异较大（工具调用、消息类型、回调签名都有变更）。当前 0.3.30 已经是 0.3 系列
里修复最全的版本，继续升就是一次独立的框架迁移，不适合顺手做。

### C. 可单独升级，留到专门排期

| 包 | 当前 | 建议 |
|---|---|---|
| `chromadb` | 1.5.9 | 4 条，向量库；升级需重新验证索引读写 |
| `starlette` | 0.38.6 | 7 条，受 FastAPI 0.115 约束（见 A 组） |
| `python-multipart` | 0.0.9 | 7 条，与 starlette 同一条链路（见 A 组） |

### D. 已解决①：`python-jose` → PyJWT

**`python-jose` 3.3.0 → PyJWT 2.15.1**：4 条 CVE + 其依赖 `ecdsa` 的 1 条，共 5 条已消除。

它承担**全部认证**，是当时风险最高的依赖。迁移面很小（全仓只有 `security.py`
用到 `encode`/`decode` 两个函数），两处行为差异都做了核实：

1. 异常类型：jose 的 `JWTError` → PyJWT 的 `InvalidTokenError`
   （`ExpiredSignatureError` / `InvalidSignatureError` 都是它的子类）；
2. 令牌格式：两者都是标准 JWS，**互相可解**。实测「jose 签发 → PyJWT 解码」
   与反向都通过，因此升级不会让已登录用户掉线，回滚也无需重新登录。

**一个值得记住的教训**：第一次把 `pyjwt` 钉在 `2.10.1`，扫描后发现它自己带
**17 条 CVE**（修复点分布在 2.12 ~ 2.15），比 python-jose 的 4 条还多。
说明「换一个更活跃的库」不等于「更安全」——**必须用扫描结果验证，而不是凭印象**。
最终选 `2.15.1`，0 条。

### E. 已解决②：LangChain 生态整组升级

| 包 | 原版本 | 现版本 |
|---|---|---|
| `langchain` | 0.3.13 | **0.3.30** |
| `langchain-core` | 0.3.40 | **0.3.86** |
| `langchain-text-splitters` | 0.3.5 | **0.3.11** |
| `langchain-openai` | 0.2.14 | **0.3.35** |
| `langchain-huggingface` | 0.1.2 | **0.3.1** |
| `python-dotenv` | 1.0.1 | **1.2.4** |
| `pydantic` | 2.9.0 | **2.9.2** |

关键点是 `langchain-huggingface`：它的 **1.x 需要 langchain-core 1.x**，
与本项目不兼容（实测 `ResolutionImpossible`），但 **0.3.1 才是匹配 0.3.x 的版本**
——依赖解析器不会主动选它，必须整组升才会落到这里。

验证（不是只看版本号）：
- 129 个后端用例全绿；
- 真实检索链路仍以 **1.0000 分**命中「退换货政策」；
- 流式生成、token 统计、LangChain 全部组件导入正常。

代价：新增 `httpx2` / `xxhash` / `zstandard` / `uuid_utils` 等传递依赖。
收益：漏洞 **34 条 → 23 条**，包数 **9 → 7**。

### 累计效果

| 阶段 | 漏洞数 | 包数 |
|---|---|---|
| 建档 | 39 | 11 |
| PyJWT 迁移后 | 34 | 9 |
| LangChain 整组升级后 | **23** | **7** |

## 为什么当初会漏掉这件事

项目里写了扩展名白名单、文件头魔数校验、生产密钥 fail-fast、限流——
这些都是**自己写的代码**里的安全措施。但对**第三方依赖**的漏洞，
之前完全没有自动化检查：没有任何一步会在「引入一个带洞的依赖」时变红。

这次补上 `scripts/security-audit.sh` + CI 里的 `security` job，把这个洞堵上。
**「只防自己写的代码，不防别人写的代码」是很典型的安全盲区。**

## 什么情况下必须立刻处理

1. 要上真实生产环境、或需要过安全评审时；
2. 某个 CVE 的利用条件与本项目实际配置吻合时（需逐条核对）；
3. 依赖本身发布了向后兼容的补丁版本时（先升，再看基线能否收紧）。

## 更新基线的正确姿势

```bash
# 1. 先升级依赖，重新扫描
bash scripts/security-audit.sh

# 2. 若确认某条洞暂时无法处理，记入基线并在上表补充理由
bash scripts/security-audit.sh --update

# 3. 必须 review diff —— 基线只增不减是最糟的情况
git diff scripts/security-baseline.json
```

> 基线只应该因为「新增了暂时无法处理的漏洞」而增长。
> 如果它一直在长而没有人回头清理，那这个机制就失效了。
