"""缓存的三层保护：击穿（单飞）、穿透（负缓存）、雪崩（TTL 抖动）。

分工：TTL 抖动是纯函数，任何时候都能测；单飞与负缓存必须真的能把值写进缓存
才有意义（缓存关闭时会退化成「每次都查」），所以标了 redis。
"""

import threading

import pytest

from app.core import cache
from app.core.cache import NEGATIVE_CACHE, cache_get_or_load, jittered_ttl


def test_ttl_jitter_stays_in_bounds():
    for _ in range(200):
        value = jittered_ttl(600, ratio=0.1)
        assert 540 <= value <= 660


def test_ttl_jitter_actually_spreads_expiry():
    """抖动必须真的打散——否则「同一批 key 同一秒一起过期」的雪崩场景没解决。"""
    values = {jittered_ttl(600, ratio=0.1) for _ in range(100)}

    assert len(values) > 1


def test_ttl_jitter_never_returns_non_positive():
    assert jittered_ttl(1, ratio=0.5) >= 1
    assert jittered_ttl(0) >= 1


def test_loads_normally_when_redis_is_down():
    """Redis 不可用时退化为「每次都查」——不能因为缓存挂了业务就跑不起来。"""
    calls = []

    result = cache_get_or_load("k", 60, lambda: calls.append(1) or {"v": 1})

    assert result == {"v": 1}
    assert len(calls) == 1


@pytest.mark.redis
def test_single_flight_loads_source_only_once(redis_db):
    """缓存击穿：热点 key 刚过期的瞬间，10 个并发请求只应该真正查一次库。"""
    calls = []
    barrier = threading.Barrier(10)
    results = []

    def loader():
        calls.append(1)
        return {"value": len(calls)}

    def worker():
        barrier.wait()  # 尽量让 10 个线程同时冲进去
        results.append(cache_get_or_load("hot-key", 60, loader))

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert len(calls) == 1, f"加载器被调用了 {len(calls)} 次，单飞没生效"
    assert all(item == {"value": 1} for item in results)


@pytest.mark.redis
def test_missing_value_is_negatively_cached(redis_db):
    """缓存穿透：查不存在的 id 也要被挡住，不能每次都打到数据库。"""
    calls = []

    for _ in range(5):
        value = cache_get_or_load(
            "missing-id", 60, lambda: calls.append(1) or None, negative_ttl=10
        )
        assert value is None

    assert len(calls) == 1


@pytest.mark.redis
def test_negative_marker_never_leaks_to_callers(redis_db):
    """负缓存内部用哨兵字符串表示「查过但没有」，对调用方仍然只是 None。"""
    assert cache_get_or_load("missing-id-2", 60, lambda: None, negative_ttl=10) is None
    assert cache.cache_get("missing-id-2") == NEGATIVE_CACHE
