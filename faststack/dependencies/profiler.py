from faststack.lib.profiler import Profiler

from ..ctx.ctx_pool import ctxpool
from ..settings import get_core_settings

profiler_ctx = ctxpool.new("profiler_ctx", default=None)


def load_profiler() -> Profiler:
    """Return a Profiler instance outside FastApi lifecycle ie celery task."""
    settings = get_core_settings()
    try:
        profiler = ctxpool.get("profiler_ctx", default=None)
        if profiler is None:
            profiler = Profiler(
                name=settings.PROFILER_NAME,
                track_memory=settings.PROFILER_TRACK_MEMORY,
                enabled=settings.PROFILER_ENABLED,
                level=settings.PROFILER_LOG_LEVEL,
            )
            profiler_ctx.set(profiler)
        return profiler
    except LookupError:
        # Context variable not set, create a new Profiler instance
        profiler = Profiler(
            name=settings.PROFILER_NAME,
            track_memory=settings.PROFILER_TRACK_MEMORY,
            enabled=settings.PROFILER_ENABLED,
            level=settings.PROFILER_LOG_LEVEL,
        )
        ctxpool.set("profiler_ctx", profiler)
        return profiler


def fetch_profiler():
    """Fetch the Profiler instance inside Depends."""
    return load_profiler()
