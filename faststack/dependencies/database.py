import sys
import uuid
from collections.abc import Iterable
from typing import Any, Callable, Dict, Type, Union

from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from ..database.engine import DBConfig
from ..database.sessions import SessionConnectionPool


class EngineMapping:
    """Mapping of session classes to their respective database engines."""

    def __init__(self):
        self._mapping = {}

    def add(self, session_class: Session, config: dict | DBConfig):
        """Add a session class and its corresponding engine to the mapping."""
        engine = DBConfig.init_engine(config)
        self._mapping[session_class] = engine

    def get(self, session_class):
        """Get the engine for a given session class."""
        return self._mapping.get(session_class)


def _init_engine(config: Any | DBConfig) -> Engine:
    """Initialize the database engine based on the provided configuration."""
    if config is None:
        return None
    return DBConfig.init_engine(config)


ENGINE_MAPPING: dict[Union[Type[Session], Type[AsyncSession]], Engine] = {}


def get_sessionmaker(sessionclass):
    """Get the sessionmaker for the database."""
    session_engine = ENGINE_MAPPING.get(sessionclass)
    if session_engine is not None:
        return sessionmaker(
            bind=session_engine,
            class_=sessionclass,
            autocommit=False,
            autoflush=False,
        )

    raise ValueError(f"Unknown session class: {sessionclass}")


def get_async_sessionmaker(sessionclass):
    """Get the async session factory for the database."""
    session_engine = ENGINE_MAPPING.get(sessionclass)
    if session_engine is not None:
        # In SQLAlchemy 1.4, we create AsyncSession directly with the async engine
        def async_session_factory():
            return sessionclass(bind=session_engine, autocommit=False, autoflush=False)

        return async_session_factory

    raise ValueError(f"Unknown async session class: {sessionclass}")


def _load_db(session_class: Union[Type[Session], Type[AsyncSession]]):
    session_connection_pool: SessionConnectionPool = SessionConnectionPool.run()
    db_session = session_connection_pool.get(session_class)
    token = None
    if db_session is None:
        if issubclass(session_class, AsyncSession):
            session_maker = get_async_sessionmaker(session_class)
        else:
            session_maker = get_sessionmaker(session_class)

        db_session = session_maker()
        token = uuid.uuid4()
        session_connection_pool.add(db_session)
    return db_session, session_connection_pool, token


async def _aload_db(session_class: Type[AsyncSession]):
    session_connection_pool: SessionConnectionPool = SessionConnectionPool.run()
    db_session = session_connection_pool.get(session_class)
    token = None
    if db_session is None:
        session_maker = get_async_sessionmaker(session_class)

        db_session = session_maker()
        token = uuid.uuid4()
        session_connection_pool.add(db_session)
    return db_session, session_connection_pool, token


def _close_db(db_session, token, session_connection_pool: SessionConnectionPool):
    if token is not None:
        db_session.close()
        session_connection_pool.delete(db_session)


async def _aclose_db(db_session, token, session_connection_pool: SessionConnectionPool):
    if token is not None:
        await db_session.close()
        await session_connection_pool.adelete(db_session)


DB_MAPPING: Dict[Union[Type[Session], Type[AsyncSession]], Callable[[], Any]] = {}

DB_SESSION_MAPPING: Dict[Union[Type[Session], Type[AsyncSession]], Callable[[], Any]] = {}


def register_session(session: Type[Session], config: Any | DBConfig):
    """Register a session with its corresponding engine."""
    # keriraj naziv engina

    engine = _init_engine(config)

    if ENGINE_MAPPING.get(session) is not None:
        raise RuntimeError(f"Session {session.__name__} is already registered with an engine.")

    ENGINE_MAPPING[session] = engine

    get_db_method_name = f"get_{session.__name__.lower()}_db"
    get_db_session_method_name = f"get_{session.__name__.lower()}_db_session"

    def generic_db_method():  # type hint won't be exact here
        try:
            db_session, session_connection_pool, token = _load_db(session)
            yield db_session
        finally:
            _close_db(db_session, token, session_connection_pool)

    def generic_db_session_method():
        """Get session outside Fastapi lifecycle ie celery tasks."""
        db_session, session_connection_pool, token = _load_db(session)
        return db_session

    generic_db_method.__name__ = get_db_method_name
    generic_db_session_method.__name__ = get_db_session_method_name
    current_module = sys.modules[__name__]

    setattr(current_module, get_db_method_name, generic_db_method)
    setattr(current_module, get_db_session_method_name, generic_db_session_method)

    if DB_MAPPING.get(session) is not None:
        raise RuntimeError(f"Session {session.__name__} is already registered with a database method.")

    DB_MAPPING[session] = generic_db_method

    if DB_SESSION_MAPPING.get(session) is not None:
        raise RuntimeError(f"Session {session.__name__} is already registered with a database session method.")

    DB_SESSION_MAPPING[session] = generic_db_session_method


def register_async_session(session: Type[AsyncSession], config: Any | DBConfig):
    """Register an async session with its corresponding engine."""
    engine = _init_engine(config)

    if ENGINE_MAPPING.get(session) is not None:
        raise RuntimeError(f"AsyncSession {session.__name__} is already registered with an engine.")

    ENGINE_MAPPING[session] = engine

    get_db_method_name = f"aget_{session.__name__.lower()}_db"
    get_db_session_method_name = f"aget_{session.__name__.lower()}_db_session"

    async def generic_async_db_method():
        try:
            db_session, session_connection_pool, token = await _aload_db(session)
            yield db_session
        finally:
            await _aclose_db(db_session, token, session_connection_pool)

    async def generic_async_db_session_method():
        """Get async session outside Fastapi lifecycle ie celery tasks."""
        db_session, session_connection_pool, token = await _aload_db(session)
        return db_session

    generic_async_db_method.__name__ = get_db_method_name
    generic_async_db_session_method.__name__ = get_db_session_method_name
    current_module = sys.modules[__name__]

    setattr(current_module, get_db_method_name, generic_async_db_method)
    setattr(current_module, get_db_session_method_name, generic_async_db_session_method)

    if DB_MAPPING.get(session) is not None:
        raise RuntimeError(f"AsyncSession {session.__name__} is already registered with a database method.")

    DB_MAPPING[session] = generic_async_db_method

    if DB_SESSION_MAPPING.get(session) is not None:
        raise RuntimeError(f"AsyncSession {session.__name__} is already registered with a database session method.")

    DB_SESSION_MAPPING[session] = generic_async_db_session_method


def register_sessions(pairs: Iterable[tuple[Union[Type[Session], Type[AsyncSession]], Any | DBConfig]]):
    """Register multiple sessions with their configs."""
    for session, config in pairs:
        if issubclass(session, AsyncSession):
            register_async_session(session, config)
        else:
            register_session(session, config)
