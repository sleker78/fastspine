from abc import ABCMeta

from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class CombinedMeta(type(DeclarativeBase), ABCMeta):  # type: ignore[misc]
    """Metaclass that combines DeclarativeBase and ABCMeta."""

    pass


class Base(DeclarativeBase, metaclass=CombinedMeta):
    """Base class for SQLAlchemy models."""

    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
