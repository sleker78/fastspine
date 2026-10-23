from rich import print as rich_print

from ..settings import get_core_settings

DEBUG_COLOR = "blue"
WARNING_COLOR = "yellow"
ERROR_COLOR = "red"
MESSAGE_COLOR = "green"


class DebugUtil:
    """A utility class for debugging."""

    @staticmethod
    def debug(message: str) -> None:
        """Log a debug message."""
        debug_mode = get_core_settings().DEBUG_MODE
        if debug_mode:
            rich_print(f"[bold {DEBUG_COLOR}]DEBUG:[/] [{MESSAGE_COLOR}]{message}[/]")

    @staticmethod
    def warning(message: str) -> None:
        """Log a warrning message."""
        rich_print(f"[bold {WARNING_COLOR}]DEBUG:[/][{MESSAGE_COLOR}]{message}[/]")

    @staticmethod
    def error(message: str) -> None:
        """Log a warrning message."""
        rich_print(f"[bold {ERROR_COLOR}]DEBUG:[/][{MESSAGE_COLOR}] {message}[/]")
