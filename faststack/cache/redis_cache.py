import gzip
import json
from typing import Any, Callable, TypeVar

from redis.exceptions import RedisError
from redis.typing import ResponseT

from ..redis.client import get_redis_client, get_sync_redis_client
from .cache_encoder import Encoder, PickledEncoder
from .cache_exception import CacheError

T = TypeVar("T", bound=Callable[..., Any])


async def cache_get(key: str, decoder: type[Encoder] = PickledEncoder, use_compression: bool = False) -> Any | None:
    """Retrieve a value from Redis cache by key."""
    try:
        redis_client = get_redis_client()
        if redis_client is None:
            return None
        cached = await redis_client.get(key)
        if cached:
            if use_compression:
                decompressed = gzip.decompress(cached)
                return decoder.decode(decompressed)
            return decoder.decode(cached)
        return None

    except (RedisError, json.JSONDecodeError) as e:
        raise CacheError(f"Cache get failed: {e!s}") from e


async def cache_set(
    key: str, value: Any, expire: int = 60, encoder: type[Encoder] = PickledEncoder, use_compression: bool = False
) -> bool:
    """Set a value in Redis cache with an optional expiration time."""
    try:
        # do not cache None values
        redis_client = get_redis_client()
        if redis_client is None:
            return False
        if value is not None:
            serialized = encoder.encode(value)
            if use_compression:
                serialized = gzip.compress(serialized)

            if expire > 0:
                return await redis_client.setex(key, expire, serialized)
            return await redis_client.set(key, serialized)
        return False
    except (RedisError, TypeError) as e:
        raise CacheError(f"Cache set failed: {e!s}") from e


async def cache_delete(key: str) -> bool:
    """Delete a key from Redis cache."""
    try:
        redis_client = get_redis_client()
        if redis_client is None:
            return False
        return await redis_client.delete(key) > 0
    except RedisError as e:
        raise CacheError(f"Cache delete failed: {e!s}") from e


def sync_cache_get(key: str, decoder: type[Encoder] = PickledEncoder, use_compression: bool = False) -> Any | None:
    """Retrieve a value from Redis cache by key."""
    try:
        client = get_sync_redis_client()
        if client is None:
            return None
        cached = client.get(key)
        if cached:
            if use_compression:
                decompressed = gzip.decompress(cached)
                return decoder.decode(decompressed)
            return decoder.decode(cached)
        return None

    except (RedisError, json.JSONDecodeError) as e:
        raise CacheError(f"Cache get failed: {str(e)}") from e


def sync_cache_set(
    key: str,
    value: Any,
    expire: int = 60,
    encoder: type[Encoder] = PickledEncoder,
    use_compression: bool = False,
) -> ResponseT | bool:
    """Set a value in Redis cache with an optional expiration time."""
    try:
        # do not cache None values
        if value is not None:
            client = get_sync_redis_client()
            if client is None:
                return False
            serialized = encoder.encode(value)
            if use_compression:
                serialized = gzip.compress(serialized)

            if expire > 0:
                return client.setex(key, expire, serialized)
            return client.set(key, serialized)
        return False
    except (RedisError, TypeError) as e:
        raise CacheError(f"Cache set failed: {str(e)}") from e


def sync_cache_delete(key: str) -> ResponseT:
    """Delete a key from Redis cache."""
    try:
        client = get_sync_redis_client()
        if client is None:
            return 0
        return client.delete(key)
    except RedisError as e:
        raise CacheError(f"Cache delete failed: {str(e)}") from e


def sync_lock(cache_key: str):
    """Context manager to lock Redis operations."""
    redis_client = get_redis_client()
    if redis_client is None:
        return None
    lock_key = f"lock:{cache_key}"
    return redis_client.lock(lock_key, timeout=100)


def lock(cache_key: str):
    """Context manager to lock Redis operations."""
    redis_client = get_redis_client()
    if redis_client is None:
        return None
    lock_key = f"lock:{cache_key}"
    return redis_client.lock(lock_key, timeout=100)


def sync_cache_size(key: str) -> int:
    """Get the number of keys in the Redis cache."""
    try:
        redis_client = get_sync_redis_client()
        if redis_client is None:
            return 0
        return redis_client.memory_usage(key) or 0
    except RedisError as e:
        raise CacheError(f"Cache size retrieval failed: {e!s}") from e


async def cache_size(key: str) -> int:
    """Get the number of keys in the Redis cache."""
    try:
        redis_client = get_redis_client()
        if redis_client is None:
            return 0
        return await redis_client.memory_usage(key) or 0
    except RedisError as e:
        raise CacheError(f"Cache size retrieval failed: {e!s}") from e
