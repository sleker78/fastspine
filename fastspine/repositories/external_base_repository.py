from abc import ABC

from ..repositories.abstract_repository import AbstractRepository


class ExternalBaseRepository(AbstractRepository, ABC):  # noqa: B024
    """Base repository class for external database operations.

    This class provides a common interface for all repository classes for externale db.
    """

    pass
