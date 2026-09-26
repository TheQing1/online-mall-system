from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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


settings = Settings()
