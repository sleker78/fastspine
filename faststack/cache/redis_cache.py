import json
from typing import Any, Callable, Type, TypeVar

from redis.exceptions import RedisError
from redis.typing import ResponseT

from ..redis.client import get_async_redis_client, get_redis_client
from .cache_encoder import Encoder, PickledEncoder
from .cache_exception import CacheError

T = TypeVar("T", bound=Callable[..., Any])


def cache_get(key: str, decoder: Type[Encoder] = PickledEncoder) -> Any | None:
    """Retrieve a value from Redis cache by key."""
    try:
        client = get_redis_client()
        cached = client.get(key)
        return decoder.decode(cached) if cached else None

    except (RedisError, json.JSONDecodeError) as e:
        raise CacheError(f"Cache get failed: {str(e)}") from e


def cache_set(key: str, value: Any, expire: int = 60, encoder: Type[Encoder] = PickledEncoder) -> ResponseT | bool:
    """Set a value in Redis cache with an optional expiration time."""
    try:
        # do not cache None values
        if value is not None:
            client = get_redis_client()
            serialized = encoder.encode(value)

            if expire > 0:
                return client.setex(key, expire, serialized)
            return client.set(key, serialized)
        return False
    except (RedisError, TypeError) as e:
        raise CacheError(f"Cache set failed: {str(e)}") from e


def cache_delete(key: str) -> ResponseT:
    """Delete a key from Redis cache."""
    try:
        client = get_redis_client()
        return client.delete(key)
    except RedisError as e:
        raise CacheError(f"Cache delete failed: {str(e)}") from e


def lock(cache_key: str):
    """Context manager to lock Redis operations."""
    lock_key = f"lock:{cache_key}"
    return get_redis_client().lock(lock_key, timeout=100)


async def cache_get_async(key: str, decoder: Type[Encoder] = PickledEncoder) -> Any | None:
    """Retrieve a value from Redis cache by key (async version)."""
    try:
        client = get_async_redis_client()
        cached = await client.get(key)
        return decoder.decode(cached) if cached else None

    except (RedisError, json.JSONDecodeError) as e:
        raise CacheError(f"Cache get failed: {str(e)}") from e


async def cache_set_async(
    key: str, value: Any, expire: int = 60, encoder: Type[Encoder] = PickledEncoder
) -> ResponseT | bool:
    """Set a value in Redis cache with an optional expiration time (async version)."""
    try:
        if value is not None:
            client = get_async_redis_client()
            serialized = encoder.encode(value)

            if expire > 0:
                return await client.setex(key, expire, serialized)
            return await client.set(key, serialized)
        return False
    except (RedisError, TypeError) as e:
        raise CacheError(f"Cache set failed: {str(e)}") from e


async def cache_delete_async(key: str) -> ResponseT:
    """Delete a key from Redis cache (async version)."""
    try:
        client = get_async_redis_client()
        return await client.delete(key)
    except RedisError as e:
        raise CacheError(f"Cache delete failed: {str(e)}") from e


async def lock_async(cache_key: str):
    """Async context manager to lock Redis operations."""
    lock_key = f"lock:{cache_key}"
    redis_lock = get_async_redis_client().lock(lock_key, timeout=100)

    class AsyncLockWrapper:
        def __init__(self, lock):
            self.lock = lock

        async def acquire(self, blocking=True):
            return await self.lock.acquire(blocking=blocking)

        async def release(self):
            return await self.lock.release()

    return AsyncLockWrapper(redis_lock)
