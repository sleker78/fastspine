import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ..database.engine import DBConfig, DBServices
from ..dependencies import database as database_module
from ..dependencies import repository_manager as repository_manager_module
from ..repositories.repository_manager import RepositoryManager
from ..settings import init_core_settings


@pytest.fixture(autouse=True, scope="session")
def _core_settings():
    """Initialize `CoreSettings` once; several modules (profiler, debug logging) require it."""
    init_core_settings()


class SyncRepoManager(RepositoryManager[Session]):
    """Sync repository manager used to test the registration/DI/cleanup lifecycle."""


class AsyncRepoManager(RepositoryManager[AsyncSession]):
    """Async repository manager used to test the registration/DI/cleanup lifecycle."""


SYNC_DB_CONFIG = DBConfig(
    dbname="test",
    user="test",
    password="test",  # noqa: S106
    host="localhost",
    port=5432,
    service=DBServices.POSTGRES,
)
ASYNC_DB_CONFIG = DBConfig(
    dbname="test",
    user="test",
    password="test",  # noqa: S106
    host="localhost",
    port=5432,
    service=DBServices.ASYNC_POSTGRES,
)


def _unregister(repo_manager_class):
    database_module.ENGINE_MAPPING.pop(repo_manager_class, None)
    database_module.DB_MAPPING.pop(repo_manager_class, None)
    repository_manager_module.manager_annotations_classes.pop(repo_manager_class, None)
    repository_manager_module._factory_cache.clear()


@pytest.fixture(autouse=True)
def _reset_repo_manager_cache():
    """Reset the repository manager cache contextvar around every test.

    It's a module-level `ContextVar`, not isolated per test by pytest, so a value left behind by
    one test would otherwise leak into the next.
    """
    repository_manager_module._repo_manager_cache_var.set(None)
    yield
    repository_manager_module._repo_manager_cache_var.set(None)


@pytest.fixture
def sync_repo_manager_class():
    """Register `SyncRepoManager`, yield it, then undo the registration."""
    database_module.register_sessions([(SyncRepoManager, SYNC_DB_CONFIG)])
    yield SyncRepoManager
    _unregister(SyncRepoManager)


@pytest.fixture
def async_repo_manager_class():
    """Register `AsyncRepoManager`, yield it, then undo the registration."""
    database_module.register_sessions([(AsyncRepoManager, ASYNC_DB_CONFIG)])
    yield AsyncRepoManager
    _unregister(AsyncRepoManager)
