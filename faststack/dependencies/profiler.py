from typing import Annotated

from fastapi import Depends, Request

from faststack.lib.profiler import Profiler

from ..ctx.ctx_pool import ctxpool

profiler_ctx = ctxpool.new("profiler_ctx", default=None)


def get_profiler(request: Request):
    """Load the Profiler instance with Depends."""
    return request.state.profiler


def load_profiler() -> Profiler:
    """Return a Profiler instance outside FastApi lifecycle ie celery task."""
    try:
        profiler = ctxpool.get("profiler_ctx", default=None)
        if profiler is None:
            profiler = Profiler()
            profiler_ctx.set(profiler)
        return profiler
    except LookupError:
        # Context variable not set, create a new Profiler instance
        profiler = Profiler()
        ctxpool.set("profiler_ctx", profiler)
        return profiler


def fetch_profiler():
    """Fetch the Profiler instance inside Depends."""
    return ctxpool.get("request_context").state.profiler


ProfilerDep = Annotated[Profiler, Depends(get_profiler)]
