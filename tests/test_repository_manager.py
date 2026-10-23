from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from faststack.repositories.abstract_repository import AbstractRepository
from faststack.repositories.repository_manager import RepositoryManager


class _FakeRepo(AbstractRepository):
    """Minimal repository: only needs `db` and `profiler`, both resolved by `RepositoryManager`."""


def test_get_lazily_creates_and_caches_the_repository():
    """A second `get()` for the same repository class returns the cached instance."""
    manager = RepositoryManager(db=Mock(spec=Session))

    first = manager.get(_FakeRepo)
    second = manager.get(_FakeRepo)

    assert first is second
    assert first.db is manager.db


def test_sync_commit_rollback_flush_delegate_to_the_session():
    """Each sync transaction method calls the matching `Session` method."""
    db = Mock(spec=Session)
    manager = RepositoryManager(db=db)

    manager.sync_commit()
    manager.sync_rollback()
    manager.sync_flush()

    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    db.flush.assert_called_once()


def test_sync_read_commit_commits_when_there_are_no_pending_changes():
    """A read-only session (no new/dirty/deleted objects) commits without complaint."""
    db = Mock(spec=Session)
    db.new = db.dirty = db.deleted = set()
    manager = RepositoryManager(db=db)

    manager.sync_read_commit()

    db.commit.assert_called_once()


def test_sync_read_commit_raises_with_pending_changes():
    """Pending changes mean it isn't actually a read-only commit; this must be caught, not silently committed."""
    db = Mock(spec=Session)
    db.new, db.dirty, db.deleted = {object()}, set(), set()
    manager = RepositoryManager(db=db)

    with pytest.raises(ValueError, match="please commit or rollback"):
        manager.sync_read_commit()

    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_async_methods_require_an_async_session():
    """`commit`/`rollback`/`flush`/`read_commit` must reject a plain sync `Session`."""
    manager = RepositoryManager(db=Mock(spec=Session))

    with pytest.raises(TypeError):
        await manager.commit()
    with pytest.raises(TypeError):
        await manager.rollback()
    with pytest.raises(TypeError):
        await manager.flush()
    with pytest.raises(TypeError):
        await manager.read_commit()


@pytest.mark.asyncio
async def test_async_methods_delegate_to_the_async_session():
    """Each async transaction method awaits the matching `AsyncSession` method."""
    db = Mock(spec=AsyncSession)
    manager = RepositoryManager(db=db)

    await manager.commit()
    await manager.rollback()
    await manager.flush()

    db.commit.assert_awaited_once()
    db.rollback.assert_awaited_once()
    db.flush.assert_awaited_once()
