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
