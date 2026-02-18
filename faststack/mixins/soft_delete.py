from sqlalchemy import Column, DateTime, event
from sqlalchemy.orm import declared_attr

from ..exception.soft_delete_exception import SoftDeleteError
from ..util.dates import now


class SoftDeleteMixin:
    """Mixin to add a deleted_at column to a SQLAlchemy model for soft deletion."""

    @declared_attr
    def deleted_at(cls):
        """Creates a deleted_at column with timezone support, defaulting to None."""
        return Column(
            DateTime(timezone=True),
            default=None,
            nullable=True,
        )

    @classmethod
    def __declare_last__(cls):
        """Intercept delete operations and convert them into soft deletes."""

        @event.listens_for(cls, "before_delete", propagate=True)
        def prevent_delete(mapper, connection, target):
            raise RuntimeError(
                f"Direct deletion of {target.__class__.__name__} is not allowed. Use soft_delete() method instead."
            )

    @property
    def is_deleted(self):
        """Check if the instance is soft deleted."""
        return self.deleted_at is not None

    def set_deleted(self) -> "SoftDeleteMixin":
        """Set the instance as soft deleted."""
        if self.is_deleted:
            raise SoftDeleteError(f"{self.__class__.__name__} is already soft deleted.")
        self.deleted_at = now()

        return self
