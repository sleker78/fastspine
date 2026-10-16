from abc import ABC
from typing import Type, final

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import BinaryExpression

from ..lib.profiler import Profiler
from ..mixins import SoftDeleteMixin
from ..models.base import Base as BaseModel
from ..repositories.abstract_repository import AbstractRepository
from ..types import DBSessions


class BaseRepository[T: BaseModel](AbstractRepository, ABC):
    """Base repository class for database operations.

    This class provides a common interface for all repository classes.
    Use this class as a base for creating specific repositories.
    Only for sqlalchemy ORM.

    Attributes:
        db (Session): The database session used for database operations.
        profiler (Profiler): The profiler instance for performance tracking.
    """

    def __init__(self, db: DBSessions, profiler: Profiler):
        """Initialize the repository with a database session and profiler.

        Args:
            db (Session): The database session used for database operations.
            profiler (Profiler): The profiler instance for performance tracking.
        """
        super().__init__(db, profiler)
        self.model = self.get_model()

    @final
    def get_model(self) -> Type[T]:
        """Get the model class associated with this repository.

        Returns:
            Type[T]: The model class associated with this repository.

        Raises:
            ValueError: If the repository does not inherit with a model type parameter.
        """
        try:
            if hasattr(self.__class__, "__orig_bases__"):
                return self.__class__.__orig_bases__[0].__args__[0]

            raise AttributeError("No __orig_bases__ found")
        except (AttributeError, IndexError) as err:
            raise ValueError("Repository {self.__class__} must inherit with model type parameter") from err

    def sync_get_by_id(self, instance_id: int) -> T | None:
        """Get an object by its ID.

        Args:
            instance_id (int): The ID of the object to retrieve.

        Returns:
            T: The object with the given ID, or None if it does not exist.
        """
        if issubclass(self.model, SoftDeleteMixin):
            return (
                self.db.query(self.model)
                .filter(self.model.id == instance_id, self.model.deleted_at.is_(None))
                .one_or_none()
            )
        return self.db.query(self.model).filter(self.model.id == instance_id).one_or_none()

    def sync_get_instance(self, instance_id: int) -> T:
        """Get an object by its ID.

        Args:
            instance_id (int): The ID of the object to retrieve.

        Returns:
            T: The object with the given ID, or None if it does not exist.
        """
        instance = self.sync_get_by_id(instance_id)
        if instance is None:
            raise ValueError(f"{self.model.__name__} with id {instance_id} does not exist.")
        return instance

    def sync_get(self, instance_id: int) -> T | None:
        """Get an object by its ID.

        Args:
            instance_id (int): The ID of the object to retrieve.

        Returns:
            T: The object with the given ID, or None if it does not exist.
        """
        return self.db.get(self.model, instance_id)

    def sync_read_commit(self) -> None:
        """Check if there are some changed/deleted or new objects and it there are no perform commit."""
        if self.db.new or self.db.dirty or self.db.deleted:
            raise ValueError(
                "There are some changes in the database session, please commit or rollback before read commit."
            )
        return self.db.commit()

    def sync_commit(self):
        """Commit the current transaction."""
        self.db.commit()

    def sync_soft_delete(self, instance: T, commit: bool = True) -> None:
        """Soft delete an object by setting its deleted_at field to the current time.

        Args:
            instance (T): The object to soft delete.
            commit (bool): Whether to commit the transaction after the operation.
        """
        if not isinstance(instance, SoftDeleteMixin):
            raise TypeError(f"{instance.__class__.__name__} does not support soft deletion.")

        instance.set_deleted()
        self.db.add(instance)
        if commit:
            self.sync_commit()

    def sync_delete(self, instance: T, commit: bool = True) -> None:
        """Delete an object from the database.

        Args:
            instance (T): The object to delete.
        """
        self.db.delete(instance)
        if commit:
            self.sync_commit()

    def sync_bulk_delete(self, ids: list[int], commit: bool = True) -> None:
        """Bulk delete objects by their IDs."""
        if issubclass(self.model, SoftDeleteMixin):
            raise TypeError(f"{self.model.__name__} does not support bulk deletion use bulk soft delete instead.")
        self.db.query(self.model).filter(self.model.id.in_(ids)).delete()

        if commit:
            self.sync_commit()

    def sync_bulk_soft_delete(self, ids: list[int], commit: bool = True) -> None:
        """Bulk soft delete objects by their IDs."""
        if not issubclass(self.model, SoftDeleteMixin):
            raise TypeError(f"{self.model.__name__} does not support bulk soft deletion.")

        instances = self.db.query(self.model).filter(self.model.id.in_(ids)).all()
        for instance in instances:
            instance.set_deleted()
            self.db.add(instance)

        if commit:
            self.sync_commit()

    def sync_count_by(self, *criterion: BinaryExpression | list[BinaryExpression]) -> int:
        """Count objects by given criteria."""
        filters = []
        # If there's one argument and it's a list, unpack it
        if len(criterion) == 1 and isinstance(criterion[0], list):
            filters = criterion[0]
        else:
            filters = list(criterion)
        if issubclass(self.model, SoftDeleteMixin):
            filters.append(self.model.deleted_at.is_(None))

        return self.db.query(self.model).filter(*filters).count()

    def sync_filter_by(self, *criterion: BinaryExpression | list[BinaryExpression]) -> list[T]:
        """Filter objects by given criteria."""
        filters = []
        # If there's one argument and it's a list, unpack it
        if len(criterion) == 1 and isinstance(criterion[0], list):
            filters = criterion[0]
        else:
            filters = list(criterion)

        return self.db.query(self.model).filter(*filters).all()

    def sync_filter_one_by(self, *criterion: BinaryExpression | list[BinaryExpression]) -> T | None:
        """Filter objects by given criteria and return one result."""
        filters = []
        # If there's one argument and it's a list, unpack it
        if len(criterion) == 1 and isinstance(criterion[0], list):
            filters = criterion[0]
        else:
            filters = list(criterion)
        if issubclass(self.model, SoftDeleteMixin):
            filters.append(self.model.deleted_at.is_(None))

        return self.db.query(self.model).filter(*filters).one_or_none()

    def sync_filter_one(self, **kwargs) -> T | None:
        """Filter objects by given criteria and return one result."""
        if issubclass(self.model, SoftDeleteMixin):
            kwargs["deleted_at"] = None
        return self.db.query(self.model).filter_by(**kwargs).one_or_none()

    def sync_create(self, instance: T, flush: bool = True, commit: bool = False) -> T:
        """Create a new object in the database.

        Args:
            instance (T): The object to create.

        Returns:
            T: The created object.
        """
        self.db.add(instance)
        if flush:
            self.db.flush()
        if commit:
            self.sync_commit()

        return instance

    async def get(self, instance_id: int) -> T | None:
        """Async get an object by its ID.

        Args:
            instance_id (int): The ID of the object to retrieve.

        Returns:
            T: The object with the given ID, or None if it does not exist.
        """
        if not isinstance(self.db, AsyncSession):
            raise TypeError("aget async method requires AsyncSession")
        return await self.db.get(self.model, instance_id)

    async def commit(self):
        """Async commit the current transaction."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("commit async method requires AsyncSession")
        await self.db.commit()

    async def read_commit(self) -> None:
        """Async check if there are some changed/deleted or new objects and if there are none perform commit."""
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

    async def get_by_id(self, instance_id: int) -> T | None:
        """Async get an object by its ID.

        Args:
            instance_id (int): The ID of the object to retrieve.

        Returns:
            T: The object with the given ID, or None if it does not exist.
        """
        if not isinstance(self.db, AsyncSession):
            raise TypeError("aget_by_id async method requires AsyncSession")

        if issubclass(self.model, SoftDeleteMixin):
            result = await self.db.execute(
                select(self.model).filter(self.model.id == instance_id, self.model.deleted_at.is_(None))
            )
            return result.scalar_one_or_none()

        result = await self.db.execute(select(self.model).filter(self.model.id == instance_id))
        return result.scalar_one_or_none()

    async def get_instance(self, instance_id: int) -> T:
        """Async get an object by its ID.

        Args:
            instance_id (int): The ID of the object to retrieve.

        Returns:
            T: The object with the given ID.

        Raises:
            ValueError: If the object does not exist.
        """
        instance = await self.get_by_id(instance_id)
        if instance is None:
            raise ValueError(f"{self.model.__name__} with id {instance_id} does not exist.")
        return instance

    async def soft_delete(self, instance: T, commit: bool = True) -> None:
        """Async soft delete an object by setting its deleted_at field to the current time.

        Args:
            instance (T): The object to soft delete.
            commit (bool): Whether to commit the transaction after the operation.
        """
        if not isinstance(self.db, AsyncSession):
            raise TypeError("soft_delete async method requires AsyncSession")

        if not isinstance(instance, SoftDeleteMixin):
            raise TypeError(f"{instance.__class__.__name__} does not support soft deletion.")

        instance.set_deleted()
        self.db.add(instance)
        if commit:
            await self.commit()

    async def bulk_soft_delete(self, ids: list[int], commit: bool = True) -> None:
        """Async bulk soft delete objects by their IDs."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("bulk_soft_delete async method requires AsyncSession")

        if not issubclass(self.model, SoftDeleteMixin):
            raise TypeError(f"{self.model.__name__} does not support bulk soft deletion.")

        result = await self.db.execute(select(self.model).filter(self.model.id.in_(ids)))
        instances = result.scalars().all()
        for instance in instances:
            instance.set_deleted()
            self.db.add(instance)

        if commit:
            await self.commit()

    async def count_by(self, *criterion: BinaryExpression | list[BinaryExpression]) -> int:
        """Count objects by given criteria."""
        filters = []
        # If there's one argument and it's a list, unpack it
        if len(criterion) == 1 and isinstance(criterion[0], list):
            filters = criterion[0]
        else:
            filters = [c for c in criterion if isinstance(c, BinaryExpression)]

        stmt = select(func.count()).select_from(self.model).where(*filters)
        return (await self.db.execute(stmt)).scalar()

    async def delete(self, instance: T, commit: bool = True) -> None:
        """Async delete an object from the database.

        Args:
            instance (T): The object to delete.
            commit (bool): Whether to commit the transaction after the operation.
        """
        if not isinstance(self.db, AsyncSession):
            raise TypeError("adelete async method requires AsyncSession")

        await self.db.delete(instance)
        if commit:
            await self.commit()

    async def bulk_delete(self, ids: list[int], commit: bool = True) -> None:
        """Async bulk delete objects by their IDs."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("bulk_delete async method requires AsyncSession")

        if issubclass(self.model, SoftDeleteMixin):
            raise TypeError(f"{self.model.__name__} does not support bulk deletion use bulk soft delete instead.")

        await self.db.execute(delete(self.model).filter(self.model.id.in_(ids)))

        if commit:
            await self.commit()

    async def filter_by(self, *criterion: BinaryExpression | list[BinaryExpression]) -> list[T]:
        """Async filter objects by given criteria."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("filter_by async method requires AsyncSession")

        filters = []
        if len(criterion) == 1 and isinstance(criterion[0], list):
            filters = criterion[0]
        else:
            filters = list(criterion)

        result = await self.db.execute(select(self.model).filter(*filters))
        return result.scalars().all()

    async def filter_one_by(self, *criterion: BinaryExpression | list[BinaryExpression]) -> T | None:
        """Filter objects by given criteria and return one result."""
        filters = []
        # If there's one argument and it's a list, unpack it
        if len(criterion) == 1 and isinstance(criterion[0], list):
            filters = criterion[0]
        else:
            filters = [c for c in criterion if isinstance(c, BinaryExpression)]

        return (await self.db.execute(select(self.model).where(*filters))).scalar_one_or_none()

    async def filter_one(self, **kwargs) -> T | None:
        """Filter objects by given criteria and return one result."""
        filters = []
        for key, value in kwargs.items():
            filters.append(getattr(self.model, key) == value)

        return (await self.db.execute(select(self.model).where(*filters))).scalar_one_or_none()

    async def create(self, instance: T, flush: bool = True, commit: bool = False) -> T:
        """Async create a new object in the database.

        Args:
            instance (T): The object to create.
            flush (bool): Whether to flush the session after adding.
            commit (bool): Whether to commit the transaction after the operation.

        Returns:
            T: The created object.
        """
        if not isinstance(self.db, AsyncSession):
            raise TypeError("acreate async method requires AsyncSession")

        self.db.add(instance)
        if flush:
            await self.flush()
        if commit:
            await self.commit()

        return instance
