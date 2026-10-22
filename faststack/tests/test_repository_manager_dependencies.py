from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ..dependencies import database as database_module
from ..dependencies.repository_manager import (
    _close_sessions,
    _close_sessions_sync,
    _repo_manager_cache_var,
    get_repository_manager,
    load_repository_manager,
    repository_manager_scope,
    repository_manager_scope_sync,
)


def test_load_repository_manager_raises_if_not_registered(sync_repo_manager_class):
    """Unregister first: the fixture already registered it, this test wants the "not registered" path."""
    database_module.ENGINE_MAPPING.pop(sync_repo_manager_class, None)

    with pytest.raises(ValueError, match="is not registered"):
        load_repository_manager(sync_repo_manager_class)


def test_load_repository_manager_creates_and_caches_sync_instance(sync_repo_manager_class):
    """A second call within the same scope returns the cached instance instead of a new session."""
    first = load_repository_manager(sync_repo_manager_class)
    second = load_repository_manager(sync_repo_manager_class)

    assert isinstance(first.db, Session)
    assert first is second  # cached within the current context, not reloaded

    first.db.close()


def test_load_repository_manager_creates_async_instance(async_repo_manager_class):
    """Loading an async-registered manager gives it an `AsyncSession`."""
    manager = load_repository_manager(async_repo_manager_class)
    assert isinstance(manager.db, AsyncSession)


@pytest.mark.asyncio
async def test_close_sessions_closes_sync_and_async_sessions_without_crashing(
    sync_repo_manager_class, async_repo_manager_class
):
    """Regression test: `_close_sessions` must not blindly `await` a sync `Session.close()`."""
    sync_manager = sync_repo_manager_class(db=Mock(spec=Session))
    async_manager = async_repo_manager_class(db=AsyncMock(spec=AsyncSession))

    _repo_manager_cache_var.set({sync_repo_manager_class: sync_manager, async_repo_manager_class: async_manager})

    await _close_sessions()

    sync_manager.db.close.assert_called_once()
    async_manager.db.close.assert_awaited_once()
    assert _repo_manager_cache_var.get() is None


def test_close_sessions_sync_closes_sync_session(sync_repo_manager_class):
    """`_close_sessions_sync` closes a plain `Session` and clears the cache."""
    manager = sync_repo_manager_class(db=Mock(spec=Session))
    _repo_manager_cache_var.set({sync_repo_manager_class: manager})

    _close_sessions_sync()

    manager.db.close.assert_called_once()
    assert _repo_manager_cache_var.get() is None


def test_close_sessions_sync_skips_async_session_without_crashing(async_repo_manager_class, caplog):
    """An `AsyncSession` can't be closed from a sync scope; it must be skipped (and logged), not crash."""
    manager = async_repo_manager_class(db=AsyncMock(spec=AsyncSession))
    _repo_manager_cache_var.set({async_repo_manager_class: manager})

    _close_sessions_sync()

    manager.db.close.assert_not_called()
    assert _repo_manager_cache_var.get() is None
    assert "Cannot close an AsyncSession from a sync scope" in caplog.text


@pytest.mark.asyncio
async def test_repository_manager_scope_closes_sessions_on_exception(sync_repo_manager_class):
    """The scope's cleanup runs even when the wrapped block raises."""
    with pytest.raises(ValueError, match="boom"):
        async with repository_manager_scope():
            load_repository_manager(sync_repo_manager_class)
            raise ValueError("boom")

    assert _repo_manager_cache_var.get() is None


def test_repository_manager_scope_sync_closes_sessions_on_exception(sync_repo_manager_class):
    """The sync scope's cleanup runs even when the wrapped block raises."""
    with pytest.raises(ValueError, match="boom"):
        with repository_manager_scope_sync():
            load_repository_manager(sync_repo_manager_class)
            raise ValueError("boom")

    assert _repo_manager_cache_var.get() is None


def test_get_repository_manager_raises_if_not_registered(sync_repo_manager_class):
    """Building a factory for an unregistered manager raises instead of returning a broken one."""
    database_module.ENGINE_MAPPING.pop(sync_repo_manager_class, None)
    database_module.DB_MAPPING.pop(sync_repo_manager_class, None)

    with pytest.raises(ValueError, match="must be a valid Session or AsyncSession type"):
        get_repository_manager(sync_repo_manager_class)


def test_get_repository_manager_factory_builds_instance_with_the_injected_session(sync_repo_manager_class):
    """Regression test: the factory must inject a plain `Session`, not just `AsyncSession`."""
    factory = get_repository_manager(sync_repo_manager_class)

    fake_session = Mock(spec=Session)
    # `factory`'s declared type is a zero-arg callable (that's all FastAPI's `Depends()` needs to see);
    # at runtime it also takes `db`, which is what we're testing here.
    instance = factory(db=fake_session)  # type: ignore[call-arg]

    assert isinstance(instance, sync_repo_manager_class)
    assert instance.db is fake_session
