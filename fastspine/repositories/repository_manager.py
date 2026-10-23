from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from fastspine.lib.profiler import Profiler

from ..dependencies.profiler import load_profiler
from ..types import DBSessions
from ..util.class_util import get_annotations
from .abstract_repository import AbstractRepository


class RepositoryManager[SESSION_T: DBSessions]:
    """Manages different repositories in the application."""

    def __init__(self, db: SESSION_T):
        self.db: SESSION_T = db
        self._repositories: dict[type[AbstractRepository], AbstractRepository] = {}

    def get[REPO_T: AbstractRepository](self, repository_class: type[REPO_T]) -> REPO_T:
        """Get a repository instance, creating it if it doesn't exist."""
        if repository_class not in self._repositories:
            self._repositories[repository_class] = self._load_repository_instance(repository_class)
        return cast(REPO_T, self._repositories[repository_class])

    def sync_commit(self):
        """Commit the current transaction."""
        self.db.commit()

    def sync_read_commit(self):
        """Commit the current read-only transaction."""
        if self.db.new or self.db.dirty or self.db.deleted:
            raise ValueError(
                "There are some changes in the database session, please commit or rollback before read commit."
            )
        return self.db.commit()

    def sync_rollback(self):
        """Rollback the current transaction."""
        self.db.rollback()

    def sync_flush(self):
        """Flush the current transaction."""
        self.db.flush()

    async def commit(self):
        """Async commit the current transaction."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("acommit async method requires AsyncSession")
        await self.db.commit()

    async def read_commit(self):
        """Async commit the current read-only transaction."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("aread_commit async method requires AsyncSession")
        if self.db.new or self.db.dirty or self.db.deleted:
            raise ValueError(
                "There are some changes in the database session, please commit or rollback before read commit."
            )
        return await self.db.commit()

    async def rollback(self):
        """Async rollback the current transaction."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("rollback async method requires AsyncSession")
        await self.db.rollback()

    async def flush(self):
        """Async flush the current transaction."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("flush async method requires AsyncSession")
        await self.db.flush()

    def _load_repository_instance[REPO_T: AbstractRepository](self, repo_class: type[REPO_T]) -> REPO_T:
        """Load repository.

        load_repository is a utility function designed to create and return an instance of a repository class.
        It is primarily used for dependency injection (DI) in contexts where FastAPI's Depends mechanism
        is not available, such as background tasks or external services like Celery.
        """
        annotations = get_annotations(repo_class, mandatory_params=["db", "profiler"])
        dependencies: dict[str, Any] = {}

        for param_name, param_type in annotations.items():
            if (isinstance(param_type, type) and issubclass(param_type, (Session, AsyncSession))) or (
                hasattr(param_type, "__bound__")
                and param_type.__bound__ in (Session, AsyncSession)
                or (
                    hasattr(param_type, "__args__")
                    and any(
                        isinstance(arg, type) and issubclass(arg, (Session, AsyncSession))
                        for arg in param_type.__args__
                    )
                )
            ):
                dependencies[param_name] = self.db
            elif param_type is Profiler:
                dependencies[param_name] = load_profiler()

        return repo_class(**dependencies)
