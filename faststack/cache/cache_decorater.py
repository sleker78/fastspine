from datetime import timedelta
from functools import wraps
from inspect import iscoroutinefunction
from typing import Any, Callable, TypeVar, cast

from fastapi import HTTPException, Request

from ..ctx.ctx_pool import ctxpool
from ..dependencies.profiler import fetch_profiler
from .cache_encoder import CacheResponseEncoder, PickledEncoder
from .cache_exception import CacheError
from .key_builder import KeyBuilder
from .redis_cache import cache_get, cache_set, lock, sync_cache_get, sync_cache_set, sync_lock

T = TypeVar("T", bound=Callable[..., Any])


def _log_cache_hit(function_name: str, cache_key: str) -> None:
    profiler = fetch_profiler()
    profiler.info("Cache hit", extra={"function": function_name, "cache_key": cache_key, "checkpoint": 1})


def _log_cache_miss(function_name: str, cache_key: str) -> None:
    profiler = fetch_profiler()
    profiler.info("Cache miss", extra={"function": function_name, "cache_key": cache_key, "checkpoint": -1})


def _log_cache_error(function_name: str, cache_key: str, error: Exception) -> None:
    profiler = fetch_profiler()
    profiler.error(
        "Cache error",
        extra={"function": function_name, "cache_key": cache_key, "error": str(error), "checkpoint": 0},
    )


def cache_response(
    expire: int | timedelta = 60,
    version: str = "v1",
    key_prefix: str = "cache",
    exclude_params: list[str] | None = None,
    ignore_errors: bool = True,
):
    """Decorator to cache the response in routes of an sync route."""

    def decorator(func: T) -> T:
        if (not iscoroutinefunction(func)) and not callable(func):
            raise TypeError("The decorated function must be callable or an async function.")

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
            if redis_lock is None:
                return await func(*args, **kwargs)

            acquired = False
            try:
                if request.headers.get("X-Cache-Bypass") == "true":
                    result = await func(*args, **kwargs)
                    await cache_set(cache_key, result, int(expire_seconds), CacheResponseEncoder)
                    return result

                cached = await cache_get(cache_key, CacheResponseEncoder)

                if cached is not None:
                    return cached
                acquired = await redis_lock.acquire(blocking=True, timeout=30)
                if not acquired:
                    raise RuntimeError("Failed to acquire Redis lock")
                cached = await cache_get(cache_key, CacheResponseEncoder)

                if cached is not None:
                    return cached
                result = await func(*args, **kwargs)
                if isinstance(result, Exception):
                    return result  # Return error response without caching
                await cache_set(cache_key, result, int(expire_seconds), CacheResponseEncoder)
                return result

            except CacheError as e:
                if not ignore_errors:
                    raise HTTPException(status_code=500, detail=f"Cache operation failed: {str(e)}") from e
                return await func(*args, **kwargs)
            finally:
                if acquired:
                    await redis_lock.release()

        return cast(T, wrapper)

    return decorator


def cache_method_async(
    expire: int | timedelta = 60,
    version: str = "v1",
    key_prefix: str = "cache",
    ignore_errors: bool = True,
    use_compression: bool = False,
    log_cache_hits: bool = False,
    log_cache_misses: bool = False,
    log_cache_errors: bool = False,
):
    """Decorator to cache the response of an async function."""

    def decorator(func: T) -> T:
        expire_seconds = expire.total_seconds() if isinstance(expire, timedelta) else expire
        if (not iscoroutinefunction(func)) and not callable(func):
            raise TypeError("The decorated function must be callable or an async function.")

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper function to handle caching logic."""
            cache_key = KeyBuilder.key_builder(
                func,
                namespace=f"{key_prefix}:{version}",
                args=args,
                kwargs=kwargs,
            )

            redis_lock = lock(cache_key)
            if redis_lock is None:
                if log_cache_misses:
                    _log_cache_miss(func.__name__, cache_key)
                return await func(*args, **kwargs)

            acquired = False
            try:
                cached = await cache_get(cache_key, PickledEncoder, use_compression=use_compression)

                if cached is not None:
                    if log_cache_hits:
                        _log_cache_hit(func.__name__, cache_key)
                    return cached

                acquired = await redis_lock.acquire(blocking=True)

                if not acquired:
                    raise RuntimeError("Failed to acquire Redis lock")
                cached = await cache_get(cache_key, PickledEncoder, use_compression=use_compression)

                if cached is not None:
                    if log_cache_hits:
                        _log_cache_hit(func.__name__, cache_key)
                    return cached

                if log_cache_misses:
                    _log_cache_miss(func.__name__, cache_key)
                result = await func(*args, **kwargs)

                if isinstance(result, Exception):
                    return result  # Return error response without caching

                await cache_set(cache_key, result, int(expire_seconds), PickledEncoder, use_compression=use_compression)

                return result

            except CacheError as e:
                if not ignore_errors:
                    raise HTTPException(status_code=500, detail=f"Cache operation failed: {e!s}") from e
                # If cache fails, execute the original function
                if log_cache_errors:
                    _log_cache_error(func.__name__, cache_key, e)
                return await func(*args, **kwargs)
            finally:
                if acquired:
                    await redis_lock.release()

        return cast(T, async_wrapper)

    return decorator


def cache_method(
    expire: int | timedelta = 60,
    version: str = "v1",
    key_prefix: str = "cache",
    ignore_errors: bool = True,
    use_compression: bool = False,
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
            redis_lock = sync_lock(cache_key)
            if redis_lock is None:
                return func(*args, **kwargs)

            acquired = False
            try:
                cached = sync_cache_get(cache_key, PickledEncoder, use_compression=use_compression)

                if cached is not None:
                    return cached
                acquired = redis_lock.acquire(blocking=True)
                if not acquired:
                    raise RuntimeError("Failed to acquire Redis lock")

                cached = sync_cache_get(cache_key, PickledEncoder, use_compression=use_compression)
                if cached is not None:
                    return cached

                result = func(*args, **kwargs)

                if isinstance(result, Exception):
                    return result  # Return error response without caching

                sync_cache_set(cache_key, result, int(expire_seconds), PickledEncoder, use_compression=use_compression)
                return result

            except CacheError as e:
                if not ignore_errors:
                    raise HTTPException(status_code=500, detail=f"Cache operation failed: {str(e)}") from e
                return func(*args, **kwargs)
            finally:
                if acquired:
                    redis_lock.release()

        return cast(T, sync_wrapper)

    return decorator
