import contextvars
import logging
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, cast, get_args, get_origin

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session

from ..ctx.ctx_pool import ctxpool
from ..dependencies.database import DB_MAPPING, ENGINE_MAPPING, _aload_db, _load_db
from ..repositories.repository_manager import RepositoryManager

_repo_manager_cache_var: contextvars.ContextVar[
    dict[type[RepositoryManager[AsyncSession | Session]], RepositoryManager[AsyncSession | Session]] | None
] = ctxpool.new("_repo_manager_cache_var", default={})

manager_annotations_classes: dict[type[Any], dict[str, Any]] = {}
_factory_cache: dict[tuple[type, bool], Callable] = {}
logger = logging.getLogger(__name__)


async def _close_sessions():
    """Close every repository manager session `load_repository_manager` lazily opened in this context."""
    cache = ctxpool.get_context_var_value(_repo_manager_cache_var)
    try:
        for repo_manager_class, repo_manager in cache.items():
            try:
                if isinstance(repo_manager.db, AsyncSession):
                    await repo_manager.db.close()
                else:
                    repo_manager.db.close()
            except Exception:
                logger.exception(
                    "Failed to close repository manager session",
                    extra={"repo_manager_class": repo_manager_class.__name__},
                )
    finally:
        ctxpool.clear_one("_repo_manager_cache_var")


def _close_sessions_sync():
    """Close every repository manager session `load_repository_manager` lazily opened in this context."""
    cache = ctxpool.get_context_var_value(_repo_manager_cache_var)
    try:
        for repo_manager_class, repo_manager in cache.items():
            if isinstance(repo_manager.db, AsyncSession):
                logger.error(
                    "Cannot close an AsyncSession from a sync scope; the connection will leak.",
                    extra={"repo_manager_class": repo_manager_class.__name__},
                )
                continue
            try:
                repo_manager.db.close()
            except Exception:
                logger.exception(
                    "Failed to close repository manager session",
                    extra={"repo_manager_class": repo_manager_class.__name__},
                )
    finally:
        ctxpool.clear_one("_repo_manager_cache_var")


@asynccontextmanager
async def repository_manager_scope() -> AsyncGenerator[None]:
    """Scope within which `load_repository_manager` lazily opens and caches sessions, closed on exit.

    Used by non-DI scopes (e.g. a CLI command) to clean up at the end of the scope's lifetime,
    without needing to know upfront which repository managers were actually used.
    """
    try:
        yield
    finally:
        await _close_sessions()


@contextmanager
def repository_manager_scope_sync() -> Generator[None, None, None]:
    """Scope within which `load_repository_manager` lazily opens and caches sessions, closed on exit.

    Used by non-DI scopes (e.g. a Celery task or CLI command) to clean up at the end of the scope's
    lifetime, without needing to know upfront which repository managers were actually used.
    """
    try:
        yield
    finally:
        _close_sessions_sync()


def _read_manager_annotations[REPO_MANAGER_T: RepositoryManager](
    repo_manager_class: type[REPO_MANAGER_T],
) -> dict[str, type[Any]]:
    """Read repository manager annotations."""
    if repo_manager_class in manager_annotations_classes:
        return manager_annotations_classes[repo_manager_class]

    annotations = None
    if hasattr(repo_manager_class, "__orig_bases__"):
        orig_bases = getattr(repo_manager_class, "__orig_bases__", ())  # type: ignore
        for base in orig_bases:
            if get_origin(base) is RepositoryManager:
                args = get_args(base)
                if args:
                    session_class = args[0]
                    annotations = {"db": session_class}
                    break

    if annotations is None:
        raise ValueError(f"Could not determine session type for {repo_manager_class.__name__}")

    manager_annotations_classes[repo_manager_class] = annotations

    return annotations


def get_repository_manager[REPO_MANAGER_T: RepositoryManager](
    repo_manager_class: type[REPO_MANAGER_T], isolated_session: bool = False
) -> Callable[[], REPO_MANAGER_T]:
    """Get repo instance. Used for DI inside Fastapi Depends lifecycle."""
    key = (repo_manager_class, isolated_session)
    if key in _factory_cache:
        return _factory_cache[key]

    annotations = _read_manager_annotations(repo_manager_class)
    session_class = annotations.get("db") if annotations else None

    # Check if it's a Session or AsyncSession subclass or bound TypeVar
    is_session_type = False
    if session_class and isinstance(session_class, type) and issubclass(session_class, (Session, AsyncSession)):
        is_session_type = True
    elif (
        session_class
        and hasattr(session_class, "__bound__")
        and getattr(session_class, "__bound__", None) in (Session, AsyncSession)
    ):
        is_session_type = True
        session_class = session_class.__bound__

    if not is_session_type:
        raise ValueError(
            f"Parameter 'db' of {repo_manager_class.__name__} must be of type Session or AsyncSession {session_class} provided"
        )

    session_func_name = DB_MAPPING.get(repo_manager_class)

    if session_func_name is None:
        raise ValueError(
            f"Parameter 'db' of {repo_manager_class.__name__} must be a valid Session or AsyncSession type {session_class} provided"
        )

    if len(annotations) > 1:
        raise ValueError(
            f"Repository {repo_manager_class.__name__} must have exactly one Session/AsyncSession parameter"
        )

    def factory(
        db: Session | AsyncSession = Depends(session_func_name, use_cache=not isolated_session),
    ) -> REPO_MANAGER_T:
        """Factory function to create the repository manager instance."""
        dependencies = {}
        for param_name, param_type in annotations.items():
            if (isinstance(param_type, type) and issubclass(param_type, (Session, AsyncSession))) or (
                hasattr(param_type, "__bound__") and param_type.__bound__ in (Session, AsyncSession)
            ):
                dependencies[param_name] = db
        return repo_manager_class(**dependencies)

    _factory_cache[key] = factory
    return factory


def load_repository_manager[REPO_MANAGER_T: RepositoryManager](
    repo_manager_class: type[REPO_MANAGER_T],
) -> REPO_MANAGER_T:
    """Load repository manager.

    load_repository manager is a utility function designed to create and return an instance of a repository manager class.
    It is primarily used for dependency injection (DI) in contexts where FastAPI's Depends mechanism
    is not available, such as background tasks or external services like Celery.
    """
    cache = ctxpool.get_context_var_value(_repo_manager_cache_var)

    if repo_manager_class in cache:
        return cast(REPO_MANAGER_T, cache[repo_manager_class])

    engine = ENGINE_MAPPING.get(repo_manager_class)
    if engine is None:
        raise ValueError(f"{repo_manager_class.__name__} is not registered, call register_sessions() for it first.")

    if isinstance(engine, AsyncEngine):
        db_session = _aload_db(repo_manager_class)
    else:
        db_session = _load_db(repo_manager_class)

    repo_instance = repo_manager_class(db=db_session)

    new_cache = dict(cache)
    new_cache[repo_manager_class] = repo_instance
    ctxpool.set("_repo_manager_cache_var", new_cache)

    return repo_instance
