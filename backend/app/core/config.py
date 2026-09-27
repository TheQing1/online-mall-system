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
    # Chroma 返回的是余弦距离（0 表示完全相同），因此这里是「距离上限」而非相似度下限
    rag_score_threshold: float = 0.7

    # File Upload
    upload_dir: str = "static/products"
    max_upload_size: int = 2 * 1024 * 1024  # 2MB

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
