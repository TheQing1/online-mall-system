"""启动自检：把「认证被静默绕过」这类配置问题挡在启动阶段。

背景：compose 和 Settings 都带了可以直接运行的默认密钥，部署时漏配环境变量
不会有任何明显症状（服务照常起来、接口照常返回 200），但任何人都能自己签发
一枚 token 登进管理后台。所以这里把「还是默认值」列为启动问题。
"""

import asyncio

import pytest

from app.core.config import Settings, startup_problems
from app.main import app, lifespan


def test_default_jwt_secret_is_reported_as_a_problem():
    settings = Settings(jwt_secret_key="change-me", environment="development")

    problems = startup_problems(settings)

    assert any("JWT_SECRET_KEY" in problem for problem in problems)


def test_random_jwt_secret_passes():
    settings = Settings(
        jwt_secret_key="0f8c1d2e3a4b5c6d7e8f90a1b2c3d4e5",
        environment="production",
    )

    assert startup_problems(settings) == []


def test_production_refuses_to_start_with_default_secret(monkeypatch):
    """生产环境带着默认密钥启动必须直接失败，而不是打一条没人看的日志。"""
    from app.core import config

    monkeypatch.setattr(config.settings, "environment", "production")
    monkeypatch.setattr(config.settings, "jwt_secret_key", "change-me")

    async def enter_lifespan():
        async with lifespan(app):
            pass

    with pytest.raises(RuntimeError):
        asyncio.run(enter_lifespan())
