from typing import Any, Awaitable, Callable, TypeVar

from redis.exceptions import RedisError

from ..services.base_service import BaseService
from .cache_encoder import PickledEncoder
from .cache_exception import CacheError
from .cache_model import CachableModel
from .key_builder import KeyBuilder
from .redis_cache import (
    cache_delete,
    cache_get,
    cache_set,
    lock,
    sync_cache_delete,
    sync_cache_get,
    sync_cache_set,
)

T = TypeVar("T")


class CacheService(BaseService):
    """Service for managing cache operations."""

    @staticmethod
    def sync_get(plain_key: str, cls: type | None) -> Any:
        """Get a value from the cache by key and optionally deserialize it into a specific class."""
        if cls is None:
            raise ValueError("Class type cannot be None")
        cache_key = KeyBuilder.model_plain_key_builder(cls.__name__, plain_key)
        return sync_cache_get(cache_key, PickledEncoder)

    @staticmethod
    async def get(plain_key: str, cls: type | None) -> Any:
        """Get a value from the cache by key and optionally deserialize it into a specific class (async version)."""
        if cls is None:
            raise ValueError("Class type cannot be None")
        cache_key = KeyBuilder.model_plain_key_builder(cls.__name__, plain_key)
        return await cache_get(cache_key, PickledEncoder)

    @staticmethod
    def sync_set(object_instance: CachableModel) -> CachableModel:
        """Set a value in the cache with an optional expiration time."""
        if not isinstance(object_instance, CachableModel):
            raise TypeError("Object must be an instance of CachableModel")
        try:
            cache_key = KeyBuilder.model_key_builder(object_instance)

            sync_cache_set(
                key=cache_key,
                value=object_instance,
                expire=object_instance.cache_expire_seconds,
                encoder=PickledEncoder,
            )

        except RedisError as e:
            raise CacheError(f"Error setting key {cache_key} in cache: {str(e)}") from e

        return object_instance

    @staticmethod
    async def set(object_instance: CachableModel) -> CachableModel:
        """Set a value in the cache with an optional expiration time (async version)."""
        if not isinstance(object_instance, CachableModel):
            raise TypeError("Object must be an instance of CachableModel")
        try:
            cache_key = KeyBuilder.model_key_builder(object_instance)

            await cache_set(
                key=cache_key,
                value=object_instance,
                expire=object_instance.cache_expire_seconds,
                encoder=PickledEncoder,
            )

        except RedisError as e:
            raise CacheError(f"Error setting key {cache_key} in cache: {str(e)}") from e

        return object_instance

    @staticmethod
    async def fetch_cache(
        object_instance: CachableModel,
        provider: Callable[[], Awaitable[T]],
        expiration: int | None = None,
    ) -> T:
        """Get the value of a CachableModel instance."""
        if not isinstance(object_instance, CachableModel):
            raise TypeError("Object must be an instance of CachableModel")
        cache_key = KeyBuilder.model_key_builder(object_instance)
        cached_value = await cache_get(cache_key, PickledEncoder)

        if cached_value is not None:
            return cached_value

        # If not cached, call the provider to get the value
        redis_lock = lock(cache_key)
        if redis_lock is None:
            return await provider()

        acquired = False
        try:
            # stampede prevention
            acquired = await redis_lock.acquire(blocking=True)

            value = await provider()
            expire = expiration if expiration is not None else object_instance.get_cache_expire_seconds()

            # Set the value in cache
            await cache_set(
                key=cache_key,
                value=value,
                expire=expire,
                encoder=PickledEncoder,
            )
            return value
        except RedisError as e:
            raise CacheError(f"Error getting key {cache_key} from cache: {str(e)}") from e
        finally:
            if acquired:
                await redis_lock.release()

    @staticmethod
    def sync_delete_cache(object_instance: CachableModel) -> None:
        """Delete a value from the cache by object instance."""
        if not isinstance(object_instance, CachableModel):
            raise TypeError("Object must be an instance of CachableModel")
        cache_key = KeyBuilder.model_key_builder(object_instance)
        try:
            sync_cache_delete(key=cache_key)
        except RedisError as e:
            raise CacheError(f"Error deleting key {cache_key} from cache: {str(e)}") from e

    @staticmethod
    async def delete_cache(object_instance: CachableModel) -> None:
        """Delete a value from the cache by object instance (async version)."""
        if not isinstance(object_instance, CachableModel):
            raise TypeError("Object must be an instance of CachableModel")
        cache_key = KeyBuilder.model_key_builder(object_instance)
        try:
            await cache_delete(key=cache_key)
        except RedisError as e:
            raise CacheError(f"Error deleting key {cache_key} from cache: {str(e)}") from e
