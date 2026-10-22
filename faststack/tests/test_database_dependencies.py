import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session

from ..dependencies import database as database_module
from ..dependencies.database import (
    DB_MAPPING,
    ENGINE_MAPPING,
    _aload_db,
    _load_db,
    get_sessionmaker,
    register_sessions,
    unregister_sessions,
)
from .conftest import ASYNC_DB_CONFIG, SYNC_DB_CONFIG, AsyncRepoManager, SyncRepoManager


def test_register_sessions_populates_engine_and_db_mapping(sync_repo_manager_class):
    """Registering a sync manager adds it to both `ENGINE_MAPPING` and `DB_MAPPING`."""
    assert isinstance(ENGINE_MAPPING[sync_repo_manager_class], Engine)
    assert sync_repo_manager_class in DB_MAPPING


@pytest.mark.asyncio
async def test_register_async_sessions_populates_mappings(async_repo_manager_class):
    """Registering an async manager adds it to both `ENGINE_MAPPING` and `DB_MAPPING`."""
    assert isinstance(ENGINE_MAPPING[async_repo_manager_class], AsyncEngine)
    assert async_repo_manager_class in DB_MAPPING


def test_register_sessions_rejects_non_repository_manager_class():
    """`register_sessions` refuses classes that aren't `RepositoryManager` subclasses."""

    class NotAManager:
        pass

    with pytest.raises(ValueError, match="Only RepositoryManager subclasses"):
        register_sessions([(NotAManager, SYNC_DB_CONFIG)])  # type: ignore[list-item]


def test_register_sessions_rejects_async_mode_mismatch():
    """A sync `RepositoryManager[Session]` registered with an async `DBConfig` must be rejected."""
    with pytest.raises(ValueError, match="does not match"):
        register_sessions([(SyncRepoManager, ASYNC_DB_CONFIG)])


def test_register_sessions_rejects_sync_mode_mismatch():
    """An async `RepositoryManager[AsyncSession]` registered with a sync `DBConfig` must be rejected."""
    with pytest.raises(ValueError, match="does not match"):
        register_sessions([(AsyncRepoManager, SYNC_DB_CONFIG)])


def test_register_session_twice_raises(sync_repo_manager_class):
    """Registering the same manager class a second time raises instead of silently overwriting it."""
    with pytest.raises(RuntimeError, match="already registered"):
        register_sessions([(sync_repo_manager_class, SYNC_DB_CONFIG)])


def test_get_sessionmaker_binds_the_generic_session_class_not_the_manager(sync_repo_manager_class):
    """Regression test for `class_=` being the manager's session type, not the manager itself.

    Passing the `RepositoryManager` subclass as `class_=` would make `sessionmaker()()` try to
    construct a `RepositoryManager(bind=..., autocommit=..., ...)`, which doesn't accept those
    keyword arguments.
    """
    session_maker = get_sessionmaker(sync_repo_manager_class)
    assert issubclass(session_maker.class_, Session)
    assert not issubclass(session_maker.class_, sync_repo_manager_class)


def test_load_db_returns_a_session_bound_to_the_registered_engine(sync_repo_manager_class):
    """`_load_db` returns a `Session` bound to the engine registered for that manager."""
    db_session = _load_db(sync_repo_manager_class)
    try:
        assert isinstance(db_session, Session)
        assert db_session.get_bind() is ENGINE_MAPPING[sync_repo_manager_class]
    finally:
        db_session.close()


def test_aload_db_returns_an_async_session(async_repo_manager_class):
    """`_aload_db` returns an `AsyncSession` for an async-registered manager."""
    db_session = _aload_db(async_repo_manager_class)
    assert isinstance(db_session, AsyncSession)


@pytest.mark.asyncio
async def test_unregister_sessions_removes_mappings_and_disposes_engine(sync_repo_manager_class):
    """`unregister_sessions` removes the manager from both mappings and disposes its engine."""
    await unregister_sessions([sync_repo_manager_class])
    assert sync_repo_manager_class not in ENGINE_MAPPING
    assert sync_repo_manager_class not in DB_MAPPING


@pytest.mark.asyncio
async def test_unregister_sessions_rejects_non_repository_manager_class():
    """`unregister_sessions` refuses classes that aren't `RepositoryManager` subclasses."""

    class NotAManager:
        pass

    with pytest.raises(ValueError, match="Only RepositoryManager subclasses"):
        await database_module.unregister_sessions([NotAManager])  # type: ignore[list-item]
