import sys
from collections.abc import Iterable
from typing import Any, Callable, get_args, get_origin

from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from ..database.engine import DBConfig
from ..repositories.repository_manager import RepositoryManager


class EngineMapping:
    """Mapping of session classes to their respective database engines."""

    def __init__(self):
        self._mapping = {}

    def add(self, repo_manager_class: type[RepositoryManager], config: dict | DBConfig):
        """Add a repository manager class and its corresponding engine to the mapping."""
        engine = DBConfig.init_engine(config)
        self._mapping[repo_manager_class] = engine

    def get(self, repo_manager_class: type[RepositoryManager]):
        """Get the engine for a given repository manager class."""
        return self._mapping.get(repo_manager_class)


def _init_engine(config: dict | DBConfig) -> Engine | None:
    """Initialize the database engine based on the provided configuration."""
    if config is None:
        return None
    return DBConfig.init_engine(config)


ENGINE_MAPPING: dict[type[RepositoryManager], Engine] = {}

DB_MAPPING: dict[type[RepositoryManager], Callable[[], Any]] = {}


def _generic_session_arg(repo_manager_class: type[RepositoryManager]) -> type | None:
    """Get the session type a `RepositoryManager` subclass is generic over, if declared."""
    for base in getattr(repo_manager_class, "__orig_bases__", ()):
        if get_origin(base) is RepositoryManager:
            args = get_args(base)
            return args[0] if args else None
    return None


def get_sessionmaker(repo_manager_class: type[RepositoryManager]):
    """Get the sessionmaker for the database."""
    session_engine = ENGINE_MAPPING.get(repo_manager_class)
    if session_engine is not None:
        session_class = _generic_session_arg(repo_manager_class) or Session
        return sessionmaker(
            bind=session_engine,
            class_=session_class,
            autocommit=False,
            autoflush=False,
        )

    raise ValueError(f"Unknown repository manager class: {repo_manager_class}")


def get_async_sessionmaker(repo_manager_class: type[RepositoryManager]) -> async_sessionmaker[AsyncSession]:
    """Get the async session factory for the database."""
    session_engine = ENGINE_MAPPING.get(repo_manager_class)
    if session_engine is not None:
        return async_sessionmaker(session_engine, expire_on_commit=False)

    raise ValueError(f"Unknown repository manager class: {repo_manager_class}")


def _load_db(repo_manager_class: type[RepositoryManager]) -> Session:
    session_maker = get_sessionmaker(repo_manager_class)
    return session_maker()


def _aload_db(repo_manager_class: type[RepositoryManager]) -> AsyncSession:
    session_maker = get_async_sessionmaker(repo_manager_class)
    return session_maker()


def _close_db(db_session: Session):
    db_session.close()


async def _aclose_db(db_session: AsyncSession):
    await db_session.close()


def register_session(repo_manager_class: type[RepositoryManager], config: Any | DBConfig):
    """Register a session with its corresponding engine."""
    engine = _init_engine(config)

    if ENGINE_MAPPING.get(repo_manager_class) is not None:
        raise RuntimeError(f"RepositoryManager {repo_manager_class.__name__} is already registered with an engine.")

    ENGINE_MAPPING[repo_manager_class] = engine

    get_db_method_name = f"get_{repo_manager_class.__name__.lower()}_db"

    def generic_db_method():  # type hint won't be exact here
        db_session = _load_db(repo_manager_class)
        try:
            yield db_session
        finally:
            _close_db(db_session)

    generic_db_method.__name__ = get_db_method_name
    current_module = sys.modules[__name__]

    setattr(current_module, get_db_method_name, generic_db_method)

    if DB_MAPPING.get(repo_manager_class) is not None:
        raise RuntimeError(
            f"RepositoryManager {repo_manager_class.__name__} is already registered with a database method."
        )

    DB_MAPPING[repo_manager_class] = generic_db_method


def register_async_session(repo_manager_class: type[RepositoryManager], config: Any | DBConfig):
    """Register an async session with its corresponding engine."""
    engine = _init_engine(config)

    if ENGINE_MAPPING.get(repo_manager_class) is not None:
        raise RuntimeError(f"RepositoryManager {repo_manager_class.__name__} is already registered with an engine.")

    ENGINE_MAPPING[repo_manager_class] = engine

    get_db_method_name = f"aget_{repo_manager_class.__name__.lower()}_db"

    async def generic_async_db_method():
        db_session = _aload_db(repo_manager_class)
        try:
            yield db_session
        finally:
            await _aclose_db(db_session)

    generic_async_db_method.__name__ = get_db_method_name
    current_module = sys.modules[__name__]

    setattr(current_module, get_db_method_name, generic_async_db_method)

    if DB_MAPPING.get(repo_manager_class) is not None:
        raise RuntimeError(
            f"RepositoryManager {repo_manager_class.__name__} is already registered with a database method."
        )

    DB_MAPPING[repo_manager_class] = generic_async_db_method


def register_sessions(pairs: Iterable[tuple[type[RepositoryManager], Any | DBConfig]]):
    """Register multiple repository managers with their database configs."""
    for repo_manager_class, config in pairs:
        if not issubclass(repo_manager_class, RepositoryManager):
            raise ValueError(
                f"Unsupported repository manager type: {repo_manager_class}. Only RepositoryManager subclasses are supported."
            )

        session_type = _generic_session_arg(repo_manager_class)
        is_async = session_type is not None and issubclass(session_type, AsyncSession)

        db_config = DBConfig.get_db_config(config)
        if is_async != db_config.async_mode:
            raise ValueError(
                f"{repo_manager_class.__name__} is generic over {session_type}, which does not match "
                f"its config's async_mode={db_config.async_mode} (service={db_config.service})."
            )

        if is_async:
            register_async_session(repo_manager_class, config)
        else:
            register_session(repo_manager_class, config)


async def unregister_sessions(repo_manager_classes: Iterable[type[RepositoryManager]]):
    """Unregister multiple repository managers, closing their database engines."""
    for repo_manager_class in repo_manager_classes:
        if not issubclass(repo_manager_class, RepositoryManager):
            raise ValueError(
                f"Unsupported repository manager type: {repo_manager_class}. Only RepositoryManager subclasses are supported."
            )

        engine = ENGINE_MAPPING.pop(repo_manager_class, None)
        if engine is not None:
            if isinstance(engine, AsyncEngine):
                await engine.dispose()
            else:
                engine.dispose()

        DB_MAPPING.pop(repo_manager_class, None)
