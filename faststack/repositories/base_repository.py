from abc import ABC
from typing import Generic, List, Type, TypeVar, Union, final

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import BinaryExpression

from faststack.lib.profiler import Profiler

from ..mixins import SoftDeleteMixin
from ..models.base import BaseModel
from ..repositories.abstract_repository import AbstractRepository

T = TypeVar("T", bound=BaseModel)


class BaseRepository(AbstractRepository, ABC, Generic[T]):
    """Base repository class for database operations.

    This class provides a common interface for all repository classes.
    Use this class as a base for creating specific repositories.
    Only for sqlalchemy ORM.

    Attributes:
        db (Session): The database session used for database operations.
        profiler (Profiler): The profiler instance for performance tracking.
    """

    def __init__(self, db: Union[Session, AsyncSession], profiler: Profiler):
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

    def get_by_id(self, instance_id: int) -> T | None:
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

    def get_instance(self, instance_id: int) -> T:
        """Get an object by its ID.

        Args:
            instance_id (int): The ID of the object to retrieve.

        Returns:
            T: The object with the given ID, or None if it does not exist.
        """
        instance = self.get_by_id(instance_id)
        if instance is None:
            raise ValueError(f"{self.model.__name__} with id {instance_id} does not exist.")
        return instance

    def get(self, instance_id: int) -> T | None:
        """Get an object by its ID.

        Args:
            instance_id (int): The ID of the object to retrieve.

        Returns:
            T: The object with the given ID, or None if it does not exist.
        """
        return self.db.get(self.model, instance_id)

    def read_commit(self) -> None:
        """Check if there are some changed/deleted or new objects and it there are no perform commit."""
        if self.db.new or self.db.dirty or self.db.deleted:
            raise ValueError(
                "There are some changes in the database session, please commit or rollback before read commit."
            )
        return self.db.commit()

    def commit(self):
        """Commit the current transaction."""
        self.db.commit()

    def soft_delete(self, instance: T, commit: bool = True) -> None:
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
            self.commit()

    def delete(self, instance: T, commit: bool = True) -> None:
        """Delete an object from the database.

        Args:
            instance (T): The object to delete.
        """
        self.db.delete(instance)
        if commit:
            self.commit()

    def bulk_delete(self, ids: list[int], commit: bool = True) -> None:
        """Bulk delete objects by their IDs."""
        if issubclass(self.model, SoftDeleteMixin):
            raise TypeError(f"{self.model.__name__} does not support bulk deletion use bulk soft delete instead.")
        self.db.query(self.model).filter(self.model.id.in_(ids)).delete()

        if commit:
            self.commit()

    def bulk_soft_delete(self, ids: list[int], commit: bool = True) -> None:
        """Bulk soft delete objects by their IDs."""
        if not issubclass(self.model, SoftDeleteMixin):
            raise TypeError(f"{self.model.__name__} does not support bulk soft deletion.")

        instances = self.db.query(self.model).filter(self.model.id.in_(ids)).all()
        for instance in instances:
            instance.set_deleted()
            self.db.add(instance)

        if commit:
            self.commit()

    def count_by(self, *criterion: Union[BinaryExpression, List[BinaryExpression]]) -> int:
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

    def filter_by(self, *criterion: Union[BinaryExpression, List[BinaryExpression]]) -> list[T]:
        """Filter objects by given criteria."""
        filters = []
        # If there's one argument and it's a list, unpack it
        if len(criterion) == 1 and isinstance(criterion[0], list):
            filters = criterion[0]
        else:
            filters = list(criterion)

        return self.db.query(self.model).filter(*filters).all()

    def filter_one_by(self, *criterion: Union[BinaryExpression, List[BinaryExpression]]) -> T | None:
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

    def filter_one(self, **kwargs) -> T | None:
        """Filter objects by given criteria and return one result."""
        if issubclass(self.model, SoftDeleteMixin):
            kwargs["deleted_at"] = None
        return self.db.query(self.model).filter_by(**kwargs).one_or_none()

    def create(self, instance: T, flush: bool = True, commit: bool = False) -> T:
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
            self.commit()

        return instance

    async def aget(self, instance_id: int) -> T | None:
        """Async get an object by its ID.

        Args:
            instance_id (int): The ID of the object to retrieve.

        Returns:
            T: The object with the given ID, or None if it does not exist.
        """
        if not isinstance(self.db, AsyncSession):
            raise TypeError("aget async method requires AsyncSession")
        return await self.db.get(self.model, instance_id)

    async def acommit(self):
        """Async commit the current transaction."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("acommit async method requires AsyncSession")
        await self.db.commit()

    async def aread_commit(self) -> None:
        """Async check if there are some changed/deleted or new objects and if there are none perform commit."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("aread_commit async method requires AsyncSession")
        if self.db.new or self.db.dirty or self.db.deleted:
            raise ValueError(
                "There are some changes in the database session, please commit or rollback before read commit."
            )
        return await self.db.commit()

    async def arollback(self):
        """Async rollback the current transaction."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("arollback async method requires AsyncSession")
        await self.db.rollback()

    async def aflush(self):
        """Async flush the current transaction."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("aflush async method requires AsyncSession")
        await self.db.flush()

    async def aget_by_id(self, instance_id: int) -> T | None:
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

    async def aget_instance(self, instance_id: int) -> T:
        """Async get an object by its ID.

        Args:
            instance_id (int): The ID of the object to retrieve.

        Returns:
            T: The object with the given ID.

        Raises:
            ValueError: If the object does not exist.
        """
        instance = await self.aget_by_id(instance_id)
        if instance is None:
            raise ValueError(f"{self.model.__name__} with id {instance_id} does not exist.")
        return instance

    async def asoft_delete(self, instance: T, commit: bool = True) -> None:
        """Async soft delete an object by setting its deleted_at field to the current time.

        Args:
            instance (T): The object to soft delete.
            commit (bool): Whether to commit the transaction after the operation.
        """
        if not isinstance(self.db, AsyncSession):
            raise TypeError("asoft_delete async method requires AsyncSession")

        if not isinstance(instance, SoftDeleteMixin):
            raise TypeError(f"{instance.__class__.__name__} does not support soft deletion.")

        instance.set_deleted()
        self.db.add(instance)
        if commit:
            await self.acommit()

    async def abulk_soft_delete(self, ids: list[int], commit: bool = True) -> None:
        """Async bulk soft delete objects by their IDs."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("abulk_soft_delete async method requires AsyncSession")

        if not issubclass(self.model, SoftDeleteMixin):
            raise TypeError(f"{self.model.__name__} does not support bulk soft deletion.")

        result = await self.db.execute(select(self.model).filter(self.model.id.in_(ids)))
        instances = result.scalars().all()
        for instance in instances:
            instance.set_deleted()
            self.db.add(instance)

        if commit:
            await self.acommit()

    async def acount_by(self, *criterion: Union[BinaryExpression, List[BinaryExpression]]) -> int:
        """Async count objects by given criteria."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("acount_by async method requires AsyncSession")

        filters = []
        if len(criterion) == 1 and isinstance(criterion[0], list):
            filters = criterion[0]
        else:
            filters = list(criterion)
        if issubclass(self.model, SoftDeleteMixin):
            filters.append(self.model.deleted_at.is_(None))

        result = await self.db.execute(select(func.count(self.model.id)).filter(*filters))
        return result.scalar()

    async def adelete(self, instance: T, commit: bool = True) -> None:
        """Async delete an object from the database.

        Args:
            instance (T): The object to delete.
            commit (bool): Whether to commit the transaction after the operation.
        """
        if not isinstance(self.db, AsyncSession):
            raise TypeError("adelete async method requires AsyncSession")

        await self.db.delete(instance)
        if commit:
            await self.acommit()

    async def abulk_delete(self, ids: list[int], commit: bool = True) -> None:
        """Async bulk delete objects by their IDs."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("abulk_delete async method requires AsyncSession")

        if issubclass(self.model, SoftDeleteMixin):
            raise TypeError(f"{self.model.__name__} does not support bulk deletion use bulk soft delete instead.")

        await self.db.execute(delete(self.model).filter(self.model.id.in_(ids)))

        if commit:
            await self.acommit()

    async def afilter_by(self, *criterion: Union[BinaryExpression, List[BinaryExpression]]) -> list[T]:
        """Async filter objects by given criteria."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("afilter_by async method requires AsyncSession")

        filters = []
        if len(criterion) == 1 and isinstance(criterion[0], list):
            filters = criterion[0]
        else:
            filters = list(criterion)

        result = await self.db.execute(select(self.model).filter(*filters))
        return result.scalars().all()

    async def afilter_one_by(self, *criterion: Union[BinaryExpression, List[BinaryExpression]]) -> T | None:
        """Async filter objects by given criteria and return one result."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("afilter_one_by async method requires AsyncSession")

        filters = []
        if len(criterion) == 1 and isinstance(criterion[0], list):
            filters = criterion[0]
        else:
            filters = list(criterion)
        if issubclass(self.model, SoftDeleteMixin):
            filters.append(self.model.deleted_at.is_(None))

        result = await self.db.execute(select(self.model).filter(*filters))
        return result.scalar_one_or_none()

    async def afilter_one(self, **kwargs) -> T | None:
        """Async filter objects by given criteria and return one result."""
        if not isinstance(self.db, AsyncSession):
            raise TypeError("afilter_one async method requires AsyncSession")

        if issubclass(self.model, SoftDeleteMixin):
            kwargs["deleted_at"] = None

        filters = [getattr(self.model, key) == value for key, value in kwargs.items()]
        result = await self.db.execute(select(self.model).filter(*filters))
        return result.scalar_one_or_none()

    async def acreate(self, instance: T, flush: bool = True, commit: bool = False) -> T:
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
            await self.aflush()
        if commit:
            await self.acommit()

        return instance
