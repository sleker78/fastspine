from functools import lru_cache

from redis import Redis as SyncRedis
from redis.asyncio import Redis

from ..settings import get_core_settings


@lru_cache
def get_redis_client() -> Redis | None:
    """Get the Redis client instance."""
    if get_core_settings().CACHE_ENABLED:
        return Redis.from_url(get_core_settings().get_redis_url())

    return None


@lru_cache
def get_sync_redis_client() -> SyncRedis | None:
    """Get the synchronous Redis client instance."""
    if get_core_settings().CACHE_ENABLED:
        return SyncRedis.from_url(get_core_settings().get_redis_url())
    return None
