import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import models  # noqa: E402,F401
from app.core.cache import reset_client  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import get_db, get_session_factory  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.product import Product, ProductStatus  # noqa: E402
from app.models.sku import ProductSku  # noqa: E402
from app.models.user import Address, User, UserRole  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _isolate_redis():
    """默认用例不依赖 Redis：显式把它指向一个必然连不上的端口。

    两个原因：
    1. 每个用例用的是独立 SQLite 库，而 Redis 是全局的——如果本机正好跑着 Redis，
       缓存会跨用例互相污染，出现「单跑通过、全跑失败」这种最难查的 flaky；
    2. 顺带让整套测试覆盖「Redis 不可用时业务照常」这条降级路径。

    真正验证缓存/限流/分布式锁的用例在 ``tests/test_redis_features.py``，
    用 ``pytest -m redis`` 单独跑。
    """
    original = settings.redis_url
    settings.redis_url = "redis://127.0.0.1:1/0"
    reset_client()
    yield
    settings.redis_url = original
    reset_client()


@pytest.fixture()
def engine(tmp_path):
    """每个用例一个独立的 SQLite 文件，用例之间互不干扰。"""
    eng = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture()
def db(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db, session_factory):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    # SSE 端点在生成器内部自建会话，所以还要覆盖 Session 工厂
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def admin(db):
    user = User(
        username="admin_test",
        password_hash=hash_password("admin123"),
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def user(db):
    u = User(username="buyer", password_hash=hash_password("user123"))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def auth_header(client, username, password):
    res = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def create_product(db, name="测试商品", skus=None):
    product = Product(
        name=name,
        description=f"{name} 的详细描述",
        price=100,
        stock=0,
        images=[],
        category_id=None,
        status=ProductStatus.ON,
        sales=0,
    )
    db.add(product)
    db.flush()
    if skus is None:
        skus = [("默认规格", {}, 100, 10)]
    for sku_name, specs, price, stock in skus:
        db.add(
            ProductSku(
                product_id=product.id,
                name=sku_name,
                specs=specs,
                price=price,
                stock=stock,
            )
        )
    product.price = min(s[2] for s in skus)
    product.stock = sum(s[3] for s in skus)
    db.commit()
    db.refresh(product)
    return product


def create_address(db, user):
    addr = Address(
        user_id=user.id,
        receiver="张三",
        phone="13800138000",
        province="广东省",
        city="深圳市",
        district="南山区",
        detail="科技园路 1 号",
        is_default=True,
    )
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return addr
