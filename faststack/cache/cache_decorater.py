from datetime import timedelta
from functools import wraps
from inspect import iscoroutinefunction
from typing import Any, Callable, TypeVar, Union, cast

from fastapi import HTTPException, Request

from ..ctx.ctx_pool import ctxpool
from .cache_encoder import CacheResponseEncoder, PickledEncoder
from .cache_exception import CacheError
from .key_builder import KeyBuilder
from .redis_cache import cache_get, cache_set, lock

T = TypeVar("T", bound=Callable[..., Any])


def cache_response(
    expire: Union[int, timedelta] = 60,
    version: str = "v1",
    key_prefix: str = "cache",
    exclude_params: list[str] | None = None,
    ignore_errors: bool = True,
):
    """Decorator to cache the response in routes of an async function."""

    def decorator(func: T) -> T:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper function to handle caching logic."""
            request: Request | None = ctxpool.get("request_context")
            if request is None:
                raise RuntimeError("Request object is required for cache_response")

            if request.method != "GET":
                raise HTTPException(
                    status_code=405,
                    detail="Cache response is only applicable for GET requests",
                )

            expire_seconds = expire.total_seconds() if isinstance(expire, timedelta) else expire
            params = {**request.path_params, **request.query_params}
            if exclude_params:
                for param in exclude_params:
                    params.pop(param, None)
            cache_key = KeyBuilder.request_key_builder(
                func=func,
                version=version,
                key_prefix=key_prefix,
                params=params,
            )
            redis_lock = lock(cache_key)
            acquired = False
            try:
                if request.headers.get("X-Cache-Bypass") == "true":
                    result = await func(*args, **kwargs)
                    cache_set(cache_key, result, int(expire_seconds), CacheResponseEncoder)
                    return result

                cached = cache_get(cache_key, CacheResponseEncoder)

                if cached is not None:
                    return cached
                acquired = redis_lock.acquire(blocking=True, timeout=30)
                result = await func(*args, **kwargs)
                if isinstance(result, Exception):
                    return result  # Return error response without caching
                cache_set(cache_key, result, int(expire_seconds), CacheResponseEncoder)
                return result

            except CacheError as e:
                if not ignore_errors:
                    raise HTTPException(status_code=500, detail=f"Cache operation failed: {str(e)}") from e
                return await func(*args, **kwargs)
            finally:
                if acquired:
                    redis_lock.release()

        return cast(T, wrapper)

    return decorator


def cache_method_async(
    expire: Union[int, timedelta] = 60,
    version: str = "v1",
    key_prefix: str = "cache",
    ignore_errors: bool = True,
):
    """Decorator to cache the response of an async function."""

    def decorator(func: T) -> T:
        expire_seconds = expire.total_seconds() if isinstance(expire, timedelta) else expire
        if (not iscoroutinefunction(func)) and not callable(func):
            raise TypeError("The decorated function must be callable or an async function.")

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper function to handle caching logic."""
            result = None
            cache_key = KeyBuilder.key_builder(
                func,
                namespace=f"{key_prefix}:{version}",
                args=args,
                kwargs=kwargs,
            )
            redis_lock = lock(cache_key)
            acquired = False
            try:
                cached = cache_get(cache_key, PickledEncoder)

                if cached is not None:
                    return cached

                acquired = redis_lock.acquire(blocking=True)
                if not acquired:
                    raise RuntimeError("Failed to acquire Redis lock")
                result = await func(*args, **kwargs)

                if isinstance(result, Exception):
                    return result  # Return error response without caching
                cache_set(cache_key, result, int(expire_seconds), PickledEncoder)
                return result

            except CacheError as e:
                if not ignore_errors:
                    raise HTTPException(status_code=500, detail=f"Cache operation failed: {str(e)}") from e
                return result if result is not None else None
            finally:
                if acquired:
                    redis_lock.release()

        return cast(T, async_wrapper)

    return decorator


def cache_method(
    expire: Union[int, timedelta] = 60,
    version: str = "v1",
    key_prefix: str = "cache",
    exclude_params: list[str] | None = None,
    ignore_errors: bool = True,
):
    """Decorator to cache the response of an sync function."""

    def decorator(func: T) -> T:
        expire_seconds = expire.total_seconds() if isinstance(expire, timedelta) else expire
        if (iscoroutinefunction(func)) and not callable(func):
            raise TypeError("The decorated function must be callable or an sync function.")

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper function to handle caching logic."""
            result = None
            cache_key = KeyBuilder.key_builder(
                func,
                namespace=f"{key_prefix}:{version}",
                args=args,
                kwargs=kwargs,
            )
            redis_lock = lock(cache_key)
            acquired = False
            try:
                cached = cache_get(cache_key, PickledEncoder)

                if cached is not None:
                    return cached
                acquired = redis_lock.acquire(blocking=True)
                if not acquired:
                    raise RuntimeError("Failed to acquire Redis lock")
                result = func(*args, **kwargs)

                if isinstance(result, Exception):
                    return result  # Return error response without caching
                cache_set(cache_key, result, int(expire_seconds), PickledEncoder)
                return result

            except CacheError as e:
                if not ignore_errors:
                    raise HTTPException(status_code=500, detail=f"Cache operation failed: {str(e)}") from e
                return result if result is not None else None
            finally:
                if acquired:
                    redis_lock.release()

        return cast(T, sync_wrapper)

    return decorator
