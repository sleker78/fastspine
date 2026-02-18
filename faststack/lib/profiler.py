import logging
import os
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional, Tuple

import psutil

logger = logging.getLogger(__name__)


@dataclass
class ProfileMetrics:
    """Container for profiling metrics."""

    duration: float = 0.0
    memory_usage: float = 0.0
    peak_memory: float = 0.0
    call_count: int = 0
    timestamp: float = field(default_factory=time.time)


class Profiler:
    """Advanced performance profiler with timing, memory tracking, and checkpoint capabilities.

    This class provides comprehensive profiling including:
    - Automatic timing with checkpoints
    - Memory usage tracking
    - Thread-safe operations
    - Context manager support
    - Named operation tracking
    """

    def __init__(self, name: str = "default", track_memory: bool = False) -> None:
        """Initialize profiler with current timestamp.

        Args:
            name: Name of this profiler instance
            track_memory: Whether to track memory usage
        """
        self._name = name
        self._track_memory = track_memory
        self._start_time = time.time()
        self._last_timestamp = 0.0
        self._checkpoints: Dict[str, List[ProfileMetrics]] = defaultdict(list)
        self._lock = threading.RLock()
        self._process = psutil.Process(os.getpid()) if track_memory else None
        self._start_memory = self._get_memory_usage() if track_memory else 0.0

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        if not self._process:
            return 0.0
        try:
            return self._process.memory_info().rss / 1024 / 1024
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    def _create_metrics(self, elapsed: float) -> ProfileMetrics:
        """Create ProfileMetrics with current state."""
        current_memory = self._get_memory_usage() if self._track_memory else 0.0
        return ProfileMetrics(
            duration=elapsed,
            memory_usage=current_memory,
            peak_memory=max(current_memory, getattr(self, "_peak_memory", 0.0)),
            call_count=1,
            timestamp=time.time(),
        )

    @contextmanager
    def checkpoint(self, name: str) -> Generator[ProfileMetrics, None, None]:
        """Context manager for named checkpoints with automatic metrics collection.

        Args:
            name: Name of the checkpoint

        Yields:
            ProfileMetrics object that gets updated on exit
        """
        with self._lock:
            start_time = time.time()
            start_memory = self._get_memory_usage() if self._track_memory else 0.0

            metrics = ProfileMetrics(timestamp=start_time)

            try:
                yield metrics
            finally:
                end_time = time.time()
                elapsed = end_time - start_time
                end_memory = self._get_memory_usage() if self._track_memory else 0.0

                metrics.duration = elapsed
                metrics.memory_usage = end_memory - start_memory
                metrics.peak_memory = end_memory

                self._checkpoints[name].append(metrics)

    def get_checkpoint_stats(self, name: str) -> Optional[Dict[str, float]]:
        """Get statistics for a named checkpoint.

        Args:
            name: Name of the checkpoint

        Returns:
            Dictionary with avg_duration, total_calls, avg_memory_usage, etc.
        """
        with self._lock:
            if name not in self._checkpoints or not self._checkpoints[name]:
                return None

            metrics = self._checkpoints[name]
            return {
                "total_calls": len(metrics),
                "avg_duration": sum(m.duration for m in metrics) / len(metrics),
                "total_duration": sum(m.duration for m in metrics),
                "min_duration": min(m.duration for m in metrics),
                "max_duration": max(m.duration for m in metrics),
                "avg_memory_usage": sum(m.memory_usage for m in metrics) / len(metrics) if self._track_memory else 0.0,
                "peak_memory": max(m.peak_memory for m in metrics) if self._track_memory else 0.0,
            }

    def stamp(self, message: str, checkpoint_name: Optional[str] = None) -> Tuple[float, str]:
        """Create timestamp for message with elapsed time and optional checkpoint.

        Args:
            message: The message to timestamp
            checkpoint_name: Optional checkpoint name to record

        Returns:
            Tuple of (elapsed_seconds, formatted_message)
        """
        with self._lock:
            elapsed = time.time() - self._start_time
            memory_info = ""

            if self._track_memory:
                current_memory = self._get_memory_usage()
                memory_delta = current_memory - self._start_memory
                memory_info = f" [mem: {current_memory:.1f}MB, Δ{memory_delta:+.1f}MB]"

            formatted_message = f"{message} @{elapsed:.3f}s{memory_info}"

            if checkpoint_name:
                metrics = self._create_metrics(elapsed)
                self._checkpoints[checkpoint_name].append(metrics)

            return elapsed, formatted_message

    def log(self, level: int, message: str, *args: Any, checkpoint_name: Optional[str] = None, **kwds: Any) -> None:
        """Log message with automatic timing and memory information.

        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, etc.)
            message: Message to log
            *args: Additional arguments for message formatting
            checkpoint_name: Optional checkpoint name to record metrics
            **kwds: Additional keyword arguments for logger
        """
        with self._lock:
            elapsed, timed_message = self.stamp(message, checkpoint_name)
            time_delta = elapsed - self._last_timestamp
            self._last_timestamp = elapsed

            # Prepare extra timing data
            extra_data: Dict[str, Any] = kwds.get("extra", {})
            extra_data.update(
                {
                    "profiler_name": self._name,
                    "duration": elapsed,
                    "time_delta": time_delta,
                    "checkpoint_name": checkpoint_name,
                }
            )

            if self._track_memory:
                extra_data["memory_usage"] = self._get_memory_usage()
                extra_data["memory_delta"] = self._get_memory_usage() - self._start_memory

            # Update kwargs with timing data
            log_kwargs = dict(kwds)
            log_kwargs["extra"] = extra_data
            log_kwargs.setdefault("stacklevel", 3)

            logger.log(level, timed_message, *args, **log_kwargs)

    def debug(self, message: str, *args: Any, checkpoint_name: Optional[str] = None, **kwds: Any) -> None:
        """Log debug message with timing information."""
        self.log(logging.DEBUG, message, *args, checkpoint_name=checkpoint_name, **kwds)

    def info(self, message: str, *args: Any, checkpoint_name: Optional[str] = None, **kwds: Any) -> None:
        """Log info message with timing information."""
        self.log(logging.INFO, message, *args, checkpoint_name=checkpoint_name, **kwds)

    def warn(self, message: str, *args: Any, checkpoint_name: Optional[str] = None, **kwds: Any) -> None:
        """Log warning message with timing information."""
        self.log(logging.WARNING, message, *args, checkpoint_name=checkpoint_name, **kwds)

    def warning(self, message: str, *args: Any, checkpoint_name: Optional[str] = None, **kwds: Any) -> None:
        """Log warning message with timing information."""
        self.log(logging.WARNING, message, *args, checkpoint_name=checkpoint_name, **kwds)

    def error(self, message: str, *args: Any, checkpoint_name: Optional[str] = None, **kwds: Any) -> None:
        """Log error message with timing information."""
        self.log(logging.ERROR, message, *args, checkpoint_name=checkpoint_name, **kwds)

    @property
    def elapsed_time(self) -> float:
        """Get total elapsed time since profiler creation."""
        return time.time() - self._start_time

    @property
    def name(self) -> str:
        """Get profiler name."""
        return self._name

    @property
    def memory_usage(self) -> float:
        """Get current memory usage in MB."""
        return self._get_memory_usage()

    @property
    def memory_delta(self) -> float:
        """Get memory delta since profiler creation in MB."""
        return self._get_memory_usage() - self._start_memory

    def get_all_checkpoint_names(self) -> List[str]:
        """Get list of all checkpoint names."""
        with self._lock:
            return list(self._checkpoints.keys())

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive profiler summary."""
        with self._lock:
            summary: Dict[str, Any] = {
                "name": self._name,
                "total_elapsed_time": self.elapsed_time,
                "memory_tracking_enabled": self._track_memory,
                "current_memory_usage": self._get_memory_usage() if self._track_memory else None,
                "memory_delta": self.memory_delta if self._track_memory else None,
                "checkpoint_count": len(self._checkpoints),
                "checkpoints": {},
            }

            for name in self._checkpoints:
                stats = self.get_checkpoint_stats(name)
                if stats:
                    summary["checkpoints"][name] = stats

            return summary

    def clear_checkpoints(self, name: Optional[str] = None) -> None:
        """Clear checkpoints.

        Args:
            name: Specific checkpoint name to clear, or None to clear all
        """
        with self._lock:
            if name is None:
                self._checkpoints.clear()
            elif name in self._checkpoints:
                del self._checkpoints[name]

    def reset(self) -> None:
        """Reset profiler timing to current moment and clear checkpoints."""
        with self._lock:
            self._start_time = time.time()
            self._last_timestamp = 0.0
            self._start_memory = self._get_memory_usage() if self._track_memory else 0.0
            self._checkpoints.clear()
