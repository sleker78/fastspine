from unittest.mock import Mock

import pytest

from ..cache import cache_decorater, redis_cache
from ..cache.cache_exception import CacheError
from ..ctx.ctx_pool import ctxpool


class _FakeAsyncLock:
    """A real-`async def` stand-in for an async redis-py `Lock`."""

    def __init__(self):
        self.locked = False

    async def acquire(self, blocking=True, timeout=None):
        self.locked = True
        return True

    async def release(self):
        self.locked = False


class _FakeSyncLock:
    """A plain stand-in for a sync redis-py `Lock`."""

    def __init__(self):
        self.locked = False

    def acquire(self, blocking=True, timeout=None):
        self.locked = True
        return True

    def release(self):
        self.locked = False


class _FakeAsyncRedis:
    """In-memory async Redis double shared by the cache + lock calls a decorator makes."""

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


class _FakeSyncRedis:
    """In-memory sync Redis double shared by the cache + lock calls a decorator makes."""

    def __init__(self):
        self.store: dict[str, bytes] = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value):
        self.store[key] = value
        return True

    def setex(self, key, _ttl, value):
        self.store[key] = value
        return True

    def delete(self, key):
        return 1 if self.store.pop(key, None) is not None else 0

    def lock(self, _name, timeout=100):
        return _FakeSyncLock()


@pytest.fixture
def fake_async_redis(monkeypatch):
    """Patch `redis_cache`'s async client getter, used by `cache_response`/`cache_method_async`.

    `cache_get`/`lock`/etc. were imported by name into `cache_decorater`, but they still resolve
    `get_redis_client` via their own `__globals__` - the `redis_cache` module they were defined in.
    """
    client = _FakeAsyncRedis()
    monkeypatch.setattr(redis_cache, "get_redis_client", lambda: client)
    return client


@pytest.fixture
def fake_sync_redis(monkeypatch):
    """Patch `redis_cache`'s sync client getter, used by `cache_method`."""
    client = _FakeSyncRedis()
    monkeypatch.setattr(redis_cache, "get_sync_redis_client", lambda: client)
    return client


@pytest.fixture
def cache_disabled(monkeypatch):
    """Patch both client getters to report caching as disabled (returns `None`)."""
    monkeypatch.setattr(redis_cache, "get_redis_client", lambda: None)
    monkeypatch.setattr(redis_cache, "get_sync_redis_client", lambda: None)


def _fake_request(method="GET", path_params=None, query_params=None, headers=None):
    request = Mock()
    request.method = method
    request.path_params = path_params or {}
    request.query_params = query_params or {}
    request.headers = Mock()
    request.headers.get = Mock(return_value=(headers or {}).get("X-Cache-Bypass"))
    return request


# --- cache_response (async, request-scoped) -------------------------------------------------


@pytest.mark.asyncio
async def test_cache_response_caches_across_calls(fake_async_redis):
    """Regression test: a second call must be a cache hit, not re-run the handler.

    This only passes if every `cache_get`/`cache_set`/lock `acquire`/`release` call the decorator
    makes is actually `await`ed - a missing `await` leaves an un-awaited coroutine instead of the
    real result, so the "was it cached?" check never sees real data.
    """
    ctxpool.set("request_context", _fake_request())
    calls = 0

    @cache_decorater.cache_response()
    async def handler():
        nonlocal calls
        calls += 1
        return {"value": calls}

    first = await handler()
    second = await handler()

    assert first == {"value": 1}
    assert second == {"value": 1}
    assert calls == 1


@pytest.mark.asyncio
async def test_cache_response_bypasses_cache_when_requested(fake_async_redis):
    """The `X-Cache-Bypass` header forces a fresh call and refreshes the cached value."""
    ctxpool.set("request_context", _fake_request(headers={"X-Cache-Bypass": "true"}))
    calls = 0

    @cache_decorater.cache_response()
    async def handler():
        nonlocal calls
        calls += 1
        return {"value": calls}

    result = await handler()

    assert result == {"value": 1}
    assert calls == 1


@pytest.mark.asyncio
async def test_cache_response_rejects_non_get_requests(fake_async_redis):
    """Only `GET` requests are cacheable; anything else is a client error."""
    ctxpool.set("request_context", _fake_request(method="POST"))

    @cache_decorater.cache_response()
    async def handler():
        return {"value": 1}

    with pytest.raises(cache_decorater.HTTPException):
        await handler()


@pytest.mark.asyncio
async def test_cache_response_requires_a_request_context():
    """Without a request in context, the decorator can't build a cache key at all."""
    ctxpool.clear_one("request_context")

    @cache_decorater.cache_response()
    async def handler():
        return {"value": 1}

    with pytest.raises(RuntimeError, match="Request object is required"):
        await handler()


@pytest.mark.asyncio
async def test_cache_response_runs_uncached_when_cache_is_disabled(cache_disabled):
    """Regression test: with no redis client, the lock is `None` - must not crash on `.acquire()`."""
    ctxpool.set("request_context", _fake_request())
    calls = 0

    @cache_decorater.cache_response()
    async def handler():
        nonlocal calls
        calls += 1
        return {"value": calls}

    first = await handler()
    second = await handler()

    assert first == {"value": 1}
    assert second == {"value": 2}  # never cached, so every call re-runs the handler
    assert calls == 2


# --- cache_method_async -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_method_async_caches_across_calls(fake_async_redis):
    """Same cross-call caching contract as `cache_response`, for plain async methods."""
    calls = 0

    @cache_decorater.cache_method_async()
    async def handler(x):
        nonlocal calls
        calls += 1
        return x * 2

    assert await handler(21) == 42
    assert await handler(21) == 42
    assert calls == 1


@pytest.mark.asyncio
async def test_cache_method_async_runs_uncached_when_cache_is_disabled(cache_disabled):
    """Already had the `redis_lock is None` guard; confirm it still behaves correctly."""
    calls = 0

    @cache_decorater.cache_method_async()
    async def handler():
        nonlocal calls
        calls += 1
        return calls

    assert await handler() == 1
    assert await handler() == 2


@pytest.mark.asyncio
async def test_cache_method_async_falls_back_to_the_function_on_cache_error(fake_async_redis, monkeypatch):
    """A `CacheError` from the cache layer doesn't take the whole call down (when ignored)."""

    async def _raise(*args, **kwargs):
        raise CacheError("boom")

    monkeypatch.setattr(cache_decorater, "cache_get", _raise)

    @cache_decorater.cache_method_async()
    async def handler():
        return "fresh"

    assert await handler() == "fresh"


# --- cache_method (sync) ----------------------------------------------------------------------


def test_cache_method_caches_across_calls(fake_sync_redis):
    """Regression test: the sync path must also be safe to call with caching enabled."""
    calls = 0

    @cache_decorater.cache_method()
    def handler(x):
        nonlocal calls
        calls += 1
        return x * 2

    assert handler(21) == 42
    assert handler(21) == 42
    assert calls == 1


def test_cache_method_runs_uncached_when_cache_is_disabled(cache_disabled):
    """Regression test: `cache_method` crashed on `.acquire()` when the lock was `None`."""
    calls = 0

    @cache_decorater.cache_method()
    def handler():
        nonlocal calls
        calls += 1
        return calls

    assert handler() == 1
    assert handler() == 2
