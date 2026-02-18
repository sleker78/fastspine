from abc import ABC, abstractmethod
from typing import final


class OwnerBase(ABC):
    """Abstract base class for objects that have an owner."""

    @abstractmethod
    def get_owner(self) -> str:
        """Get the owner of the object."""
        pass

    @final
    def is_owner(self, email: str) -> bool:
        """Check if the given email is the owner of the object."""
        return self.get_owner() == email
