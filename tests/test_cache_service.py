import pytest

from fastspine.cache import cache_service, redis_cache
from fastspine.cache.cache_model import CachableModel
from fastspine.cache.cache_service import CacheService


class _Widget(CachableModel):
    """A minimal `CachableModel` for exercising `CacheService`."""

    widget_id: str

    def get_cache_identifier(self) -> str:
        return self.widget_id

    def get_cache_expire_seconds(self) -> int:
        return 60


class _FakeAsyncLock:
    """A real-`async def` stand-in for an async redis-py `Lock`."""

    async def acquire(self, blocking=True, timeout=None):
        return True

    async def release(self):
        pass


class _FakeAsyncRedis:
    """In-memory async Redis double."""

    def __init__(self):
        self.store: dict[str, bytes] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value):
        self.store[key] = value
        return True

    async def setex(self, key, _ttl, value):
        self.store[key] = value
        return True

    async def delete(self, key):
        return 1 if self.store.pop(key, None) is not None else 0

    def lock(self, _name, timeout=100):
        return _FakeAsyncLock()


@pytest.fixture
def fake_async_redis(monkeypatch):
    """Patch `redis_cache`'s async client getter, used by `CacheService`/`cache_service`."""
    client = _FakeAsyncRedis()
    monkeypatch.setattr(redis_cache, "get_redis_client", lambda: client)
    return client


@pytest.mark.asyncio
async def test_fetch_cache_calls_the_provider_on_a_miss_and_caches_the_result(fake_async_redis):
    """Regression test: `lock()` is sync, not awaitable - this used to crash with a `TypeError`."""
    widget = _Widget(widget_id="w1")
    calls = 0

    async def provider():
        nonlocal calls
        calls += 1
        return {"value": calls}

    first = await cache_service.CacheService.fetch_cache(widget, provider)
    second = await cache_service.CacheService.fetch_cache(widget, provider)

    assert first == {"value": 1}
    assert second == {"value": 1}  # second call is a cache hit, provider not called again
    assert calls == 1


@pytest.mark.asyncio
async def test_fetch_cache_calls_the_provider_directly_when_cache_is_disabled(monkeypatch):
    """With no redis client, `lock()` returns `None` - must not crash on `.acquire()`."""
    monkeypatch.setattr(redis_cache, "get_redis_client", lambda: None)
    widget = _Widget(widget_id="w1")

    result = await CacheService.fetch_cache(widget, lambda: _async_const({"value": 1}))

    assert result == {"value": 1}


async def _async_const(value):
    return value
