import contextvars
from typing import Any, Callable, Dict, Type, TypeVar, Union, get_args, get_origin

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ..ctx.ctx_pool import ctxpool
from ..dependencies.database import DB_MAPPING, DB_SESSION_MAPPING
from ..repositories.repository_manager import RepositoryManager

REPO_MANAGER_T = TypeVar("REPO_MANAGER_T", bound=RepositoryManager)
_repo_manager_cache_var: contextvars.ContextVar[dict] = ctxpool.new("_repo_manager_cache_var", default={})

manager_annotations_classes: Dict[Type[Any], Dict[str, Any]] = {}


def clear_repository_manager_cache():
    """Clear service cache."""
    ctxpool.clear_one("_repo_manager_cache_var")


def _is_valid_session_instance(param_type: Type, session_class: Type) -> bool:
    """Check if the parameter type is a valid instance of the session class."""
    if isinstance(param_type, type) and issubclass(param_type, session_class):
        return True
    if hasattr(param_type, "__bound__") and param_type.__bound__ in (Session, AsyncSession):
        return True
    if hasattr(param_type, "__args__") and any(
        isinstance(arg, type) and issubclass(arg, (Session, AsyncSession)) for arg in param_type.__args__
    ):
        return True
    return False


def _read_manager_annotations(repo_manager_class: Type[REPO_MANAGER_T]) -> dict[str, Type]:
    """Read repository manager annotations."""
    if repo_manager_class in manager_annotations_classes:
        return manager_annotations_classes[repo_manager_class]

    annotations = None
    if hasattr(repo_manager_class, "__orig_bases__"):
        orig_bases = getattr(repo_manager_class, "__orig_bases__", ())  # type: ignore
        for base in orig_bases:
            if get_origin(base) is RepositoryManager:
                args = get_args(base)
                args = get_args(base)
                if args:
                    session_class = args[0]
                    annotations = {"db": session_class}
                    break

    if annotations is None:
        raise ValueError(f"Could not determine session type for {repo_manager_class.__name__}")

    manager_annotations_classes[repo_manager_class] = annotations

    return annotations


def get_repository_manager(repo_manager_class: Type[REPO_MANAGER_T]) -> Callable[[], REPO_MANAGER_T]:
    """Get repo instance. Used for DI inside Fastapi Depends lifecycle."""
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

    session_func_name = DB_MAPPING.get(session_class) if session_class else None

    if session_func_name is None:
        raise ValueError(
            f"Parameter 'db' of {repo_manager_class.__name__} must be a valid Session or AsyncSession type {session_class} provided"
        )

    if len(annotations) > 1:
        raise ValueError(
            f"Repository {repo_manager_class.__name__} must have exactly one Session/AsyncSession parameter"
        )

    def factory(db: Union[Session, AsyncSession] = Depends(session_func_name)) -> REPO_MANAGER_T:
        """Factory function to create the repository manager instance."""
        dependencies = {}
        for param_name, param_type in annotations.items():
            if (isinstance(param_type, type) and issubclass(param_type, (Session, AsyncSession))) or (
                hasattr(param_type, "__bound__") and param_type.__bound__ in (Session, AsyncSession)
            ):
                dependencies[param_name] = db
        return repo_manager_class(**dependencies)

    return factory


def load_repository_manager(repo_manager_class: Type[REPO_MANAGER_T]) -> REPO_MANAGER_T:
    """Load repository manager.

    load_repository manager is a utility function designed to create and return an instance of a repository manager class.
    It is primarily used for dependency injection (DI) in contexts where FastAPI's Depends mechanism
    is not available, such as background tasks or external services like Celery.
    """
    cache = ctxpool.get("_repo_manager_cache_var", default={})

    if repo_manager_class in cache:
        return cache[repo_manager_class]

    annotations = _read_manager_annotations(repo_manager_class)
    session_class = annotations.get("db") if annotations else None

    if session_class is None:
        raise ValueError(f"Could not determine session type for {repo_manager_class.__name__}")
    # Handle TypeVar bound sessions
    if hasattr(session_class, "__bound__") and session_class.__bound__ in (Session, AsyncSession):
        session_class = session_class.__bound__

    session_func_name = DB_SESSION_MAPPING.get(session_class)
    if not callable(session_func_name):
        raise ValueError(
            f"Parameter 'db' of {repo_manager_class.__name__} must be a valid Session or AsyncSession type"
        )
    dependencies = {}

    for param_name, param_type in annotations.items():
        # Check for Session or AsyncSession types
        if (isinstance(param_type, type) and issubclass(param_type, (Session, AsyncSession))) or (
            hasattr(param_type, "__bound__") and param_type.__bound__ in (Session, AsyncSession)
        ):
            dependencies[param_name] = session_func_name()

    repo_instance = repo_manager_class(**dependencies)

    new_cache = dict(cache)
    new_cache[repo_manager_class] = repo_instance
    ctxpool.set("_repo_manager_cache_var", new_cache)

    return repo_instance


def repository_manager_dep(repo_class: Type[REPO_MANAGER_T]) -> REPO_MANAGER_T:
    """Repository dependency."""
    return Depends(get_repository_manager(repo_class))
