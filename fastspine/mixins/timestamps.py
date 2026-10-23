import datetime

from sqlalchemy import Column, DateTime
from sqlalchemy.orm import declared_attr


class CreatedAtMixin:
    """Mixin to add a created_at column to a SQLAlchemy model."""

    @declared_attr
    def created_at(cls):
        """Creates a created_at column with the current UTC time as default."""
        return Column(
            DateTime(timezone=True),
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
            nullable=False,
            onupdate=None,
        )


class UpdatedAtMixin:
    """Mixin to add an updated_at column to a SQLAlchemy model."""

    @declared_attr
    def updated_at(cls):
        """Creates an updated_at column with the current UTC time as default."""
        return Column(
            DateTime, default=None, onupdate=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=True
        )


class TimestampMixin(CreatedAtMixin, UpdatedAtMixin):
    """Mixin to add created_at and updated_at columns to a SQLAlchemy model."""

    pass
