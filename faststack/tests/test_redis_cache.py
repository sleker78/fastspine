import pytest

from ..cache import redis_cache
from ..cache.cache_encoder import PickledEncoder
from ..cache.cache_exception import CacheError


class _FakeAsyncRedis:
    """A tiny in-memory stand-in for `redis.asyncio.Redis`, with real `async def` methods."""

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

    async def memory_usage(self, key):
        return len(self.store[key]) if key in self.store else None


class _FakeSyncRedis:
    """A tiny in-memory stand-in for `redis.Redis`."""

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

    def memory_usage(self, key):
        return len(self.store[key]) if key in self.store else None


@pytest.fixture
def fake_async_redis(monkeypatch):
    """Patch `redis_cache`'s async client getter to return an in-memory fake."""
    client = _FakeAsyncRedis()
    monkeypatch.setattr(redis_cache, "get_redis_client", lambda: client)
    return client


@pytest.fixture
def fake_sync_redis(monkeypatch):
    """Patch `redis_cache`'s sync client getter to return an in-memory fake."""
    client = _FakeSyncRedis()
    monkeypatch.setattr(redis_cache, "get_sync_redis_client", lambda: client)
    return client


@pytest.fixture
def cache_disabled(monkeypatch):
    """Patch both client getters to report caching as disabled (returns `None`)."""
    monkeypatch.setattr(redis_cache, "get_redis_client", lambda: None)
    monkeypatch.setattr(redis_cache, "get_sync_redis_client", lambda: None)


# --- async ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_set_and_get_round_trip(fake_async_redis):
    """A value set via `cache_set` is retrievable via `cache_get`, decoded back to itself."""
    await redis_cache.cache_set("k", {"a": 1}, expire=60, encoder=PickledEncoder)

    assert await redis_cache.cache_get("k", decoder=PickledEncoder) == {"a": 1}


@pytest.mark.asyncio
async def test_cache_set_and_get_round_trip_with_compression(fake_async_redis):
    """`use_compression=True` must round-trip too, not just the uncompressed path."""
    await redis_cache.cache_set("k", {"a": 1}, expire=60, encoder=PickledEncoder, use_compression=True)

    assert await redis_cache.cache_get("k", decoder=PickledEncoder, use_compression=True) == {"a": 1}


@pytest.mark.asyncio
async def test_cache_get_returns_none_for_a_missing_key(fake_async_redis):
    """A cache miss returns `None`, not an exception."""
    assert await redis_cache.cache_get("missing", decoder=PickledEncoder) is None


@pytest.mark.asyncio
async def test_cache_set_does_not_store_none_values(fake_async_redis):
    """`None` is treated as "nothing to cache", not a cacheable value."""
    stored = await redis_cache.cache_set("k", None, expire=60, encoder=PickledEncoder)

    assert stored is False
    assert "k" not in fake_async_redis.store


@pytest.mark.asyncio
async def test_cache_delete_reports_whether_a_key_existed(fake_async_redis):
    """Delete reports `True` only if a key was actually removed."""
    await redis_cache.cache_set("k", "v", expire=60, encoder=PickledEncoder)

    assert await redis_cache.cache_delete("k") is True
    assert await redis_cache.cache_delete("k") is False


@pytest.mark.asyncio
async def test_async_helpers_are_no_ops_when_cache_is_disabled(cache_disabled):
    """Regression test: every async helper must degrade gracefully, not crash, when disabled."""
    assert await redis_cache.cache_get("k", decoder=PickledEncoder) is None
    assert await redis_cache.cache_set("k", "v", encoder=PickledEncoder) is False
    assert await redis_cache.cache_delete("k") is False
    assert await redis_cache.cache_size("k") == 0
    assert redis_cache.lock("k") is None


# --- sync ------------------------------------------------------------------------------------


def test_sync_cache_set_and_get_round_trip(fake_sync_redis):
    """Sync counterpart of the async round-trip test."""
    redis_cache.sync_cache_set("k", {"a": 1}, expire=60, encoder=PickledEncoder)

    assert redis_cache.sync_cache_get("k", decoder=PickledEncoder) == {"a": 1}


def test_sync_cache_set_and_get_round_trip_with_compression(fake_sync_redis):
    """Regression test: `sync_cache_set`/`sync_cache_get` must support `use_compression` too."""
    redis_cache.sync_cache_set("k", {"a": 1}, expire=60, encoder=PickledEncoder, use_compression=True)

    assert redis_cache.sync_cache_get("k", decoder=PickledEncoder, use_compression=True) == {"a": 1}


def test_sync_cache_delete_reports_whether_a_key_existed(fake_sync_redis):
    """Sync counterpart of the async delete-reporting test."""
    redis_cache.sync_cache_set("k", "v", expire=60, encoder=PickledEncoder)

    assert redis_cache.sync_cache_delete("k") == 1
    assert redis_cache.sync_cache_delete("k") == 0


def test_sync_helpers_are_no_ops_when_cache_is_disabled(cache_disabled):
    """Regression test: every sync helper must degrade gracefully, not crash, when disabled."""
    assert redis_cache.sync_cache_get("k", decoder=PickledEncoder) is None
    assert redis_cache.sync_cache_set("k", "v", encoder=PickledEncoder) is False
    assert redis_cache.sync_cache_delete("k") == 0
    assert redis_cache.sync_cache_size("k") == 0
    assert redis_cache.sync_lock("k") is None


def test_sync_cache_get_wraps_decode_errors(fake_sync_redis):
    """A corrupt cached payload surfaces as `CacheError`, not a raw decode exception."""
    fake_sync_redis.store["k"] = b"not a pickle"

    with pytest.raises(CacheError):
        redis_cache.sync_cache_get("k", decoder=PickledEncoder)
