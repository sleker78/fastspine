"""A Typer app whose async commands get repository managers scoped to the command's lifetime.

FastAPI's `Depends()`-based session lifecycle (open on request start, close on request end) has no
equivalent outside a request. `command_scope` provides that equivalent for CLI commands: repository
managers are opened lazily, on first use, by `load_repository_manager` (which caches them for the
duration of the command, so repeated calls within one command reuse the same manager/session instead
of each opening a fresh one); `command_scope` closes whatever ended up being opened once the command
finishes - whether it succeeded or raised.
"""

import asyncio
import functools
import inspect
from collections.abc import Awaitable, Callable

import typer

from ..dependencies.repository_manager import repository_manager_scope


def command_scope[**P, R](fn: Callable[P, Awaitable[R]]) -> Callable[P, R]:
    """Wrap an async Typer command, closing whatever repository manager sessions it opened."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        async def _main() -> R:
            async with repository_manager_scope():
                return await fn(*args, **kwargs)

        return asyncio.run(_main())

    return wrapper


class ScopedTyper(typer.Typer):
    """Typer app that applies `command_scope` to every async command automatically."""

    def command(self, *args, **kwargs):
        """Register a command, wrapping async commands with `command_scope`."""
        register = super().command(*args, **kwargs)

        def decorator(fn):
            if inspect.iscoroutinefunction(fn):
                fn = command_scope(fn)
            return register(fn)

        return decorator
