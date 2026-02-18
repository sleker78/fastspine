from functools import lru_cache

import redis
import redis.asyncio as aioredis

from ..settings import get_core_settings


@lru_cache
def get_redis_client() -> redis.StrictRedis:
    """Get the Redis client.

    Returns:
        redis.StrictRedis: The Redis client instance.
    """
    if get_core_settings().CACHE_ENABLED:
        return redis.StrictRedis.from_url(get_core_settings().CELERY_BROKER_URI)

    raise RuntimeError(
        "Redis client is not initialized. Ensure CACHE_ENABLED is set to True and CELERY_BROKER_URI is configured correctly."
    )


@lru_cache
def get_async_redis_client() -> aioredis.Redis:
    """Get the async Redis client.

    Returns:
        aioredis.Redis: The async Redis client instance.
    """
    if get_core_settings().CACHE_ENABLED:
        return aioredis.from_url(get_core_settings().CELERY_BROKER_URI)

    raise RuntimeError(
        "Async Redis client is not initialized. Ensure CACHE_ENABLED is set to True and CELERY_BROKER_URI is configured correctly."
    )
