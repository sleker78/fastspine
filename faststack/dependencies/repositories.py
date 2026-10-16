from typing import Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from faststack.lib.profiler import Profiler

from ..ctx.ctx_pool import ctxpool
from ..dependencies.database import DB_MAPPING, DB_SESSION_MAPPING
from ..dependencies.profiler import fetch_profiler, load_profiler
from ..repositories.abstract_repository import AbstractRepository
from ..types import DBSessions
from ..util.class_util import get_annotations


def clear_cache():
    """Clear service cache."""
    ctxpool.clear_one("_repo_cache_var")


def get_repository[REPO_T: AbstractRepository](repo_class: type[REPO_T]) -> Callable[[], REPO_T]:
    """Get repo instance. Used for DI inside Fastapi Depends lifecycle."""
    annotations = get_annotations(repo_class, mandatory_params=["db"])

    session_class = annotations["db"]

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
        raise ValueError(f"Parameter 'db' of {repo_class.__name__} must be of type Session or AsyncSession")

    session_func_name = DB_MAPPING.get(session_class)

    if session_func_name is None:
        raise ValueError(f"Parameter 'db' of {repo_class.__name__} must be a valid Session or AsyncSession type")

    if len(annotations) > 2:
        raise ValueError(
            f"Repository {repo_class.__name__} must have exactly one Session/AsyncSession parameter and optional Profiler parameter"
        )

    def factory(
        db: DBSessions = Depends(session_func_name),
    ) -> REPO_T:
        """Factory function to create the repository instance."""
        dependencies = {}
        for param_name, param_type in annotations.items():
            if (isinstance(param_type, type) and issubclass(param_type, (Session, AsyncSession))) or (
                hasattr(param_type, "__bound__") and param_type.__bound__ in (Session, AsyncSession)
            ):
                dependencies[param_name] = db
            elif param_type is Profiler:
                dependencies[param_name] = fetch_profiler()

        return repo_class(**dependencies)

    return factory


def load_repository[REPO_T: AbstractRepository](repo_class: type[REPO_T]) -> REPO_T:
    """Load repository.

    load_repository is a utility function designed to create and return an instance of a repository class.
    It is primarily used for dependency injection (DI) in contexts where FastAPI's Depends mechanism
    is not available, such as background tasks or external services like Celery.
    """
    cache = ctxpool.get("_repo_cache_var", default={})

    if repo_class in cache:
        return cache[repo_class]

    annotations = get_annotations(repo_class, mandatory_params=["db", "profiler"])
    session_class = annotations["db"]

    # Handle TypeVar bound sessions
    if hasattr(session_class, "__bound__") and session_class.__bound__ in (
        Session,
        AsyncSession,
    ):
        session_class = session_class.__bound__

    session_func_name = DB_SESSION_MAPPING.get(session_class)
    dependencies = {}

    for param_name, param_type in annotations.items():
        # Check for Session or AsyncSession types
        if (isinstance(param_type, type) and issubclass(param_type, (Session, AsyncSession))) and callable(
            session_func_name
        ):
            dependencies[param_name] = session_func_name()
        elif (
            hasattr(param_type, "__bound__")
            and param_type.__bound__ in (Session, AsyncSession)
            and callable(session_func_name)
        ):
            dependencies[param_name] = session_func_name()
        elif param_type is Profiler:
            dependencies[param_name] = load_profiler()

    repo_instance = repo_class(**dependencies)

    new_cache = dict(cache)
    new_cache[repo_class] = repo_instance
    ctxpool.set("_repo_cache_var", new_cache)

    return repo_instance
