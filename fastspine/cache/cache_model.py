from abc import ABC, abstractmethod

from pydantic import BaseModel


class CachableModel(BaseModel, ABC):
    """Abstract base class for cacheable models."""

    @abstractmethod
    def get_cache_identifier(self) -> str:
        """Get a unique identifier for the cache entry.

        This identifier should be unique for each instance of the model
        and should not change over time. It is used to store and retrieve
        the cached data.
        """
        raise NotImplementedError("Subclasses must implement this method")

    @abstractmethod
    def get_cache_expire_seconds(self) -> int:
        """Get the expiration time for the cache entry in seconds.

        Use 0 for no expiration. This is useful for caching data that should not expire.
        Use a positive integer for data that should expire after a certain time.

        """
        raise NotImplementedError("Subclasses must implement this method")

    @property
    def cache_expire_seconds(self) -> int:
        """Get the expiration time for the cache entry in seconds."""
        return self.get_cache_expire_seconds()
