from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from faststack.dependencies.repository_manager import _repo_manager_cache_var
from faststack.middleware.session_middleware import DBSessionMiddleware, DBSessionMiddlewareASGI


@pytest.mark.asyncio
async def test_dispatch_closes_sync_and_async_sessions_and_clears_ctxpool(
    sync_repo_manager_class, async_repo_manager_class
):
    """Regression test for cleanup crashing on a sync-managed `RepositoryManager`.

    A manager loaded directly inside a route handler (bypassing `Depends()`) must not crash the
    middleware's cleanup, which used to `await` every cached session unconditionally.
    """
    sync_manager = sync_repo_manager_class(db=Mock(spec=Session))
    async_manager = async_repo_manager_class(db=AsyncMock(spec=AsyncSession))
    _repo_manager_cache_var.set({sync_repo_manager_class: sync_manager, async_repo_manager_class: async_manager})

    middleware = DBSessionMiddleware(app=Mock())
    call_next = AsyncMock(return_value="the-response")

    response = await middleware.dispatch(Mock(), call_next)

    assert response == "the-response"
    sync_manager.db.close.assert_called_once()
    async_manager.db.close.assert_awaited_once()
    assert _repo_manager_cache_var.get() is None


@pytest.mark.asyncio
async def test_asgi_dispatch_closes_sessions_even_if_the_app_raises(sync_repo_manager_class):
    """Cleanup still runs, via the `finally` block, when the wrapped ASGI app raises."""
    manager = sync_repo_manager_class(db=Mock(spec=Session))
    _repo_manager_cache_var.set({sync_repo_manager_class: manager})

    async def failing_app(scope, receive, send):
        raise ValueError("boom")

    middleware = DBSessionMiddlewareASGI(app=failing_app)

    with pytest.raises(ValueError, match="boom"):
        await middleware({"type": "http"}, AsyncMock(), AsyncMock())

    manager.db.close.assert_called_once()
    assert _repo_manager_cache_var.get() is None


@pytest.mark.asyncio
async def test_asgi_dispatch_ignores_non_http_scopes():
    """Non-HTTP scopes (e.g. lifespan) pass straight through, with no session cleanup attempted."""
    app = AsyncMock()
    middleware = DBSessionMiddlewareASGI(app=app)

    await middleware({"type": "lifespan"}, AsyncMock(), AsyncMock())

    app.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_closes_sessions_even_if_the_handler_raises(sync_repo_manager_class):
    """`DBSessionMiddleware.dispatch`'s cleanup must run even when `call_next` raises."""
    manager = sync_repo_manager_class(db=Mock(spec=Session))
    _repo_manager_cache_var.set({sync_repo_manager_class: manager})

    middleware = DBSessionMiddleware(app=Mock())
    call_next = AsyncMock(side_effect=ValueError("boom"))

    with pytest.raises(ValueError, match="boom"):
        await middleware.dispatch(Mock(), call_next)

    manager.db.close.assert_called_once()
    assert _repo_manager_cache_var.get() is None
