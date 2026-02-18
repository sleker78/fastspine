from abc import ABCMeta

from sqlalchemy import Column, Integer
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base


class CustomBaseMeta(DeclarativeMeta, ABCMeta):
    """Custom metaclass for SQLAlchemy models."""

    pass


class BaseModel:
    """Base model with common id column."""

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)


Base = declarative_base(cls=BaseModel, metaclass=CustomBaseMeta)
