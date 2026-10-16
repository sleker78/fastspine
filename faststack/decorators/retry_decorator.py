"""Retry helpers for transient service failures."""

import asyncio
import functools
import logging
import time
from collections.abc import Callable
from inspect import iscoroutinefunction
from typing import Any

logger = logging.getLogger(__name__)


def default_fallback(*args: Any, **kwargs: Any) -> None:
    """Raise an error after all retry attempts have failed."""
    logger.error("Function failed after all retry attempts")
    raise RuntimeError("Function failed after all retry attempts")


def retry(n_tries: int, sleep_time: float, fallback: Callable[..., Any] = default_fallback):
    """Retry synchronous or asynchronous functions after exceptions.

    Args:
        n_tries: Total number of attempts, including the initial call.
        sleep_time: Seconds to wait between failed attempts.
        fallback: Function called after all attempts fail.
    """
    if n_tries < 1:
        raise ValueError("n_tries must be at least 1")

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                for attempt in range(1, n_tries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as error:
                        logger.warning(
                            "Function attempt failed",
                            extra={"attempt": attempt, "function": func.__name__, "exception": error},
                        )
                        if attempt < n_tries:
                            await asyncio.sleep(sleep_time)
                return fallback(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(1, n_tries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as error:
                    logger.warning(
                        "Function attempt failed",
                        extra={"attempt": attempt, "function": func.__name__, "exception": error},
                    )
                    if attempt < n_tries:
                        time.sleep(sleep_time)
            return fallback(*args, **kwargs)

        return sync_wrapper

    return decorator
