from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 运行环境。production 下启动自检不通过会直接拒绝启动（见 startup_problems）
    environment: str = "development"

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

    # 本地数据目录：向量库 + Embedding 模型缓存。
    # 刻意放在 Python 包之外。此前这两者都落在 app/ 下面，而 docker-compose 用
    # named volume 挂载该路径，会把 app/models/*.py 一起遮蔽 —— 重新构建镜像后
    # 容器里跑的仍然是 volume 中的旧代码。
    data_dir: str = "data"

    @property
    def data_path(self) -> Path:
        """数据目录绝对路径；相对路径按 backend/ 解析，与启动时的工作目录无关。"""
        path = Path(self.data_dir)
        if path.is_absolute():
            return path
        # config.py -> core -> app -> backend
        return Path(__file__).resolve().parents[2] / path

    # JWT
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    order_expire_minutes: int = 30

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    # 官方模型名现为 deepseek-flash（旧名 deepseek-v4-flash 仍被接受但已退役）
    deepseek_model: str = "deepseek-flash"

    # --- RAG 检索 ---
    # vector：只用向量召回；hybrid：向量 + BM25 融合（见 app/ai/retriever.py）
    # 默认 hybrid 是实测结论：22 篇文档 / 51 条用例上 recall@1 84.3% → 90.2%。
    rag_retrieval_mode: str = "hybrid"
    # 相关性下限，0~1 且**越大越严格**（与 Chroma 的余弦距离相反）。
    # 0.3 恰好等价于原来「余弦距离 ≤ 0.7」的取值，方便对比两种模式。
    rag_min_relevance: float = 0.3
    # 混合模式的权重：扫过 0.7/0.3 ~ 0.3/0.7 五组，0.6/0.4 的 recall@1 与
    # recall@3 同时最优（见 tests/test_rag_quality.py 的对比输出）。
    rag_vector_weight: float = 0.6
    rag_bm25_weight: float = 0.4
    # 交叉编码器重排：默认关闭。开启后首次使用会下载约 1.1GB 的 bge-reranker-base，
    # 每条问题多花约 1 秒 CPU 前向；收益见 README 的对比表。
    rag_rerank_enabled: bool = False
    # 送入重排的候选条数（召回阶段会多取一些，重排后再收敛到 top-k）
    rag_rerank_candidates: int = 10

    # File Upload
    upload_dir: str = "static/products"
    max_upload_size: int = 2 * 1024 * 1024  # 2MB

    # --- Redis：缓存 / 限流 / 分布式锁 ---
    redis_url: str = "redis://localhost:6379/0"
    # 超时刻意给得很短：Redis 不可达时宁可降级，也不能把请求线程拖死
    redis_connect_timeout: float = 0.2
    # 商品详情/分类的缓存时长（秒）。下单路径靠条件 UPDATE 保证不超卖，
    # 所以展示层短暂陈旧是可以接受的，见 product_service 的说明。
    cache_product_ttl: int = 60
    # 负缓存（查不到的结果）的存活时间。短一点：既要挡住穿透，又不能让
    # 「刚上架的商品」在缓存里继续查不到。
    cache_negative_ttl: int = 30

    # --- 限流（固定窗口）---
    rate_limit_window_seconds: int = 60
    # 全站兜底配额（按用户/来源 IP）：挡住「拿到一个 token 就无限刷」以及爬虫。
    # 配成 0 表示关闭——压测时必须关，否则量到的是限流器而不是业务。
    rate_limit_api: int = 300
    rate_limit_login: int = 10
    rate_limit_order: int = 20
    rate_limit_chat: int = 20

    # --- 可观测性 ---
    # true 时输出单行 JSON 日志（便于日志系统采集），默认人类可读
    log_json: bool = False
    log_slow_request_ms: int = 500
    # 是否在 API 进程内跑定时任务。多副本部署时应设为 false，
    # 由一个独立 worker 进程负责（见 docker-compose 的 worker 服务）
    run_background_tasks: bool = True

    class Config:
        env_file = ".env"


# 示例默认值：这些密钥一望即知是占位符，绝不能带到线上。
# 只要 JWT 密钥还是其中之一，任何人都能自己签发 token 登进管理后台。
INSECURE_JWT_SECRETS = frozenset(
    {"", "change-me", "change-me-in-production", "your-secret-key-change-me"}
)


def startup_problems(s: Settings) -> list[str]:
    """启动自检：返回需要人工处理的配置问题，空列表表示没问题。

    刻意做成「启动即失败」而不是「用到的时候才报错」：compose 与 Settings
    都带了可以直接运行的默认密钥，部署时漏配环境变量不会有任何明显症状，
    但认证实际上已经被绕过。
    """
    problems = []
    if s.jwt_secret_key in INSECURE_JWT_SECRETS:
        problems.append(
            "JWT_SECRET_KEY 仍是示例默认值，任何人都能伪造登录凭证；"
            "请换成随机字符串（例如 `openssl rand -hex 32` 的输出）"
        )
    return problems


settings = Settings()
