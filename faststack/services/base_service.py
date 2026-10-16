from abc import ABC

from ..dependencies.profiler import fetch_profiler
from ..lib.profiler import Profiler


class BaseService(ABC):  # noqa: B024
    """Base service class."""

    _profiler: Profiler | None = None

    @property
    def profiler(self) -> Profiler:
        """Get the Profiler instance."""
        if self._profiler is None:
            self._profiler = fetch_profiler()

        return self._profiler
