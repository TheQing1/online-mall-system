from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_size=10,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_factory():
    """返回 Session 工厂本身。

    SSE 这类长连接响应不能用请求作用域的 ``get_db``：会话会一直持有连接
    直到流结束，客户端断连时还可能被并发关闭。改为在生成器内部按需
    创建/关闭会话。返回工厂（而不是 Session）让测试可以覆盖依赖注入。
    """
    return SessionLocal
