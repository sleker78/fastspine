from typing import Callable

from fastspine.lib.profiler import Profiler

from ..ctx.ctx_pool import ctxpool
from ..settings import get_core_settings

profiler_ctx = ctxpool.new("profiler_ctx", default=None)

_profiler_factory: Callable[[], Profiler] | None = None


def set_profiler_factory(factory: Callable[[], Profiler] | None) -> None:
    """Register a factory for building this process's `Profiler` instance.

    Call this once at process startup - same process-per-entrypoint discipline as
    `register_sessions`/`init_core_settings` (a FastAPI app, a CLI command, a Celery worker each
    need their own call, since each is a separate process) - before anything calls
    `load_profiler()`/`fetch_profiler()`. The factory takes no arguments; read
    `get_core_settings()` yourself inside it if your custom `Profiler` needs settings-driven
    behavior. Pass `None` to restore the default (a plain `Profiler` built from
    `PROFILER_NAME`/`PROFILER_TRACK_MEMORY`/`PROFILER_ENABLED`/`PROFILER_LOG_LEVEL`).

    The factory must return a `Profiler` (subclass) instance - every place a `Profiler` gets
    injected (`BaseService.profiler`, `BaseRepository.profiler`, the cache decorators) is typed
    as plain `Profiler`, not whatever custom subclass you use, so override/extend its methods
    rather than changing its public shape.
    """
    global _profiler_factory
    _profiler_factory = factory


def _build_profiler() -> Profiler:
    """Build a new `Profiler` instance, via the registered factory if one was set."""
    if _profiler_factory is not None:
        return _profiler_factory()

    settings = get_core_settings()
    return Profiler(
        name=settings.PROFILER_NAME,
        track_memory=settings.PROFILER_TRACK_MEMORY,
        enabled=settings.PROFILER_ENABLED,
        level=settings.PROFILER_LOG_LEVEL,
    )


def load_profiler() -> Profiler:
    """Return a Profiler instance outside FastApi lifecycle ie celery task."""
    profiler = ctxpool.get("profiler_ctx", default=None)
    if profiler is None:
        profiler = _build_profiler()
        profiler_ctx.set(profiler)
    return profiler


def fetch_profiler():
    """Fetch the Profiler instance inside Depends."""
    return load_profiler()
