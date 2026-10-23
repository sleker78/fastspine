import contextlib
import logging
import logging.handlers
import os
import re
import time
import uuid
from contextvars import ContextVar
from inspect import iscoroutinefunction
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator, Optional

import ecs_logging
from termcolor import colored

try:
    import celery
    import celery.signals  # Manual import needed
except ImportError:
    celery = None

_EMPTY_CONTEXT: Dict[str, Any] = {}
log_context: ContextVar[Dict[str, Any]] = ContextVar("fastspine_log_context", default=_EMPTY_CONTEXT)


class FastSpineFormatter(logging.Formatter):
    """Custom formatter class with colors, timestamps, log levels, and logger names."""

    NAME_WIDTH: int = 16

    FORMATS = {
        logging.DEBUG: (colored("%(asctime)s", "blue") + f" DEBUG %(name)-{NAME_WIDTH:d}s %(message)s"),
        logging.INFO: (
            colored("%(asctime)s", "blue")
            + colored(" INFO ", "white", attrs=["bold"])
            + f" %(name)-{NAME_WIDTH:d}s %(message)s"
        ),
        logging.WARNING: (
            colored("%(asctime)s", "blue")
            + colored(" WARN ", "yellow", attrs=["bold"])
            + colored(f" %(name)-{NAME_WIDTH:d}s %(message)s", "yellow")
        ),
        logging.ERROR: (
            colored("%(asctime)s", "light_red")
            + colored(" ERROR", "red", attrs=["bold"])
            + colored(f" %(name)-{NAME_WIDTH:d}s %(message)s", "red")
        ),
        logging.CRITICAL: (
            colored("%(asctime)s", "black", "on_magenta")
            + colored(" CRIT ", "black", "on_magenta", attrs=["bold"])
            + colored(f" %(name)-{NAME_WIDTH:d}s %(message)s", "black", "on_magenta")
        ),
    }

    def format(self, record):
        """Format the log record with colors, timestamps, log levels, and logger names."""
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)

        # Overwrite milisecond format to work with a dot.
        formatter.default_msec_format = "%s.%03d"
        return formatter.format(record)


def setup_logging(
    log_level: str = "INFO",
    file_pattern: str = "logs/elastic-{hostname}.log",
    max_bytes: int = 100_000_000,
    backup_count: int = 2,
    **kwargs,
):
    """Set up logging with a custom formatter and a rotating file handler.

    The log_level string is a space-separated list of log level instructions. See
    `parse_log_level()` for more information. The default value is INFO.
    The environment variable `LOG_LEVEL` is used and has precedence over the argument.

    The file pattern is a string that specifies the path to the log file. The
    format-string syntax can be used to inject the process ID (pid) or hostname
    (hostname) into the file path.

    The arguments max_bytes and backup_count are passed to the rotating file handler.

    Celery imposes it's own logging configuration. However, if `import celery` succeeds,
    `setup_logging()` instructs celery to use the custom logging configuration.
    """
    log_level = os.environ.get("LOG_LEVEL", log_level)

    # Fail early if the log level is invalid.
    log_levels = parse_log_level(log_level)

    # Log file
    pid = os.getpid()
    hostname = os.uname().nodename
    ecs_filename = file_pattern.format(pid=pid, hostname=hostname)
    Path(ecs_filename).parent.mkdir(parents=True, exist_ok=True)

    # Monkey patch the makeRecord method to allow for extra fields in the log record.
    # Monkey-patch is used instead of subclassing because the patch will affect existing
    # and future loggers, as well as the root logger.
    if hasattr(logging, "_loggerClass"):
        logging._loggerClass.makeRecord = make_record
    else:
        raise RuntimeError("logging module does not have _loggerClass attribute")
    # ECS logging
    ecs_handler = logging.handlers.RotatingFileHandler(ecs_filename, maxBytes=max_bytes, backupCount=backup_count)
    ecs_handler.setFormatter(
        ecs_logging.StdlibFormatter(
            # add extra fields from kwargs
            extra=kwargs,
        )
    )

    # Stdout logging
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(FastSpineFormatter())

    # This makes sure DEBUG-level messages go to elastic if the root or model-specific log
    # level is set to DEBUG.
    ecs_handler.setLevel(logging.DEBUG)
    stdout_handler.setLevel(logging.DEBUG)

    logger = logging.getLogger("root")
    logger.addHandler(ecs_handler)
    logger.addHandler(stdout_handler)

    # Set log levels
    for module, level in log_levels.items():
        logger = logging.getLogger(module)
        logger.setLevel(level)

    if celery:
        # Overwrite logging setup handler
        celery.signals.setup_logging.connect(_on_setup_logging)


def _on_setup_logging(**kwargs: Any) -> None:
    """No-op function to overwrite Celery's logging setup."""
    pass


def parse_log_level(log_level: str) -> dict[str, int]:
    """Parse a log level string and return a dictionary of log levels for each module.

    The log level string is a space-separated list of log level instructions. The first
    instruction sets the root log level, and the rest set the log levels for specific
    modules. Each instruction after the root is in the form `module=LEVEL`, where
    `module` is the name of the logger and `LEVEL` is the log level. Whitespace around
    instructions is ignored. The log level for the root logger is mandatory. All other
    instructions are optional.

    If an invalid log level instruction is provided, a ValueError is raised. By default,
    the following log level are supported: DEBUG, INFO, WARNING, ERROR, CRITICAL.

    The return value is a dictionary where the keys are the module names and the values
    are the integer-valued log levels.

    Examples:
    To set to the universal log level to WARNING, the log level string would
    be `"WARNING"`.

    To set the root log level to INFO and the log level for the `app` module
    to DEBUG, the log level string would be `"INFO app=DEBUG"`.

    To set the root log level to INFO and the log level of the `library`
    module to ERROR, the log level string would be `"INFO library=ERROR"`.
    """
    log_consts = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    mapping: dict[str, Any] = {}
    root_instruction, *instructions = re.split(r"\s+", log_level.strip())

    if root_instruction not in log_consts:
        raise ValueError(f"Invalid root log level: {root_instruction}")
    mapping["root"] = log_consts[root_instruction]

    for instruction in instructions:
        match = re.match(r"([a-zA-Z0-9_.]+)=([A-Z]+)", instruction)
        if not match:
            raise ValueError(f"Invalid log instruction: {instruction}")
        module = match.group(1)
        level = match.group(2)

        if level not in log_consts:
            raise ValueError(f"Invalid log level: {level}")
        mapping[module] = log_consts[level]

    return mapping


@contextlib.contextmanager
def contextualize(**kwargs: Any) -> Generator[Dict[str, Any], None, None]:
    """Add the current context to the logger with enhanced tracking.

    Args:
        **kwargs: Context variables to add to logging context

    Yields:
        Dict containing the current logging context

    Example:
        with contextualize(user_id=123, request_id="abc"):
            logger.info("Processing request")  # Will include user_id and request_id
    """
    # Generate correlation_id if not provided
    if "correlation_id" not in kwargs:
        kwargs["correlation_id"] = str(uuid.uuid4())

    # Add timestamp for context creation
    if "context_created_at" not in kwargs:
        kwargs["context_created_at"] = time.time()

    current_context = log_context.get()
    new_context = {**current_context, **kwargs}
    token = log_context.set(new_context)

    try:
        yield new_context
    finally:
        log_context.reset(token)


@contextlib.asynccontextmanager
async def acontextualize(**kwargs: Any) -> AsyncGenerator[Dict[str, Any], None]:
    """Async version of contextualize for use with async functions.

    Args:
        **kwargs: Context variables to add to logging context

    Yields:
        Dict containing the current logging context

    Example:
        async with acontextualize(user_id=123, request_id="abc"):
            logger.info("Processing async request")
    """
    # Generate correlation_id if not provided
    if "correlation_id" not in kwargs:
        kwargs["correlation_id"] = str(uuid.uuid4())

    # Add timestamp for context creation
    if "context_created_at" not in kwargs:
        kwargs["context_created_at"] = time.time()

    current_context = log_context.get()
    new_context = {**current_context, **kwargs}
    token = log_context.set(new_context)

    try:
        yield new_context
    finally:
        log_context.reset(token)


def get_current_context() -> Dict[str, Any]:
    """Get the current logging context.

    Returns:
        Dictionary containing current context variables
    """
    return log_context.get().copy()


def update_context(**kwargs: Any) -> None:
    """Update the current context with new values.

    Args:
        **kwargs: Context variables to add or update

    Note:
        This modifies the current context in-place. Use with caution
        in concurrent environments.
    """
    current_context = log_context.get()
    new_context = {**current_context, **kwargs}
    log_context.set(new_context)


def clear_context() -> None:
    """Clear the current logging context."""
    log_context.set({})


def with_context(context: Dict[str, Any]):
    """Decorator to add context to a function.

    Args:
        context: Context variables to add

    Example:
        @with_context({"module": "user_service"})
        def process_user(user_id):
            logger.info(f"Processing user {user_id}")
    """

    def decorator(func):
        if iscoroutinefunction(func):

            async def async_wrapper(*args, **kwargs):
                async with acontextualize(**context):
                    return await func(*args, **kwargs)

            return async_wrapper

        def sync_wrapper(*args, **kwargs):
            with contextualize(**context):
                return func(*args, **kwargs)

        return sync_wrapper

    return decorator


def make_record(
    self,
    name: str,
    level: int,
    fn: str,
    lno: int,
    msg: Any,
    args: tuple,
    exc_info,
    func: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    sinfo: Optional[str] = None,
) -> logging.LogRecord:
    """Enhanced factory method for creating LogRecords with context.

    This method is monkey-patched into the logging system to automatically
    include context variables in all log records.
    """
    rv = logging.getLogRecordFactory()(name, level, fn, lno, msg, args, exc_info, func, sinfo)
    context = log_context.get()

    if extra is None:
        extra = {}

    # Merge context with extra, giving priority to extra
    merged_extra = {**context, **extra}

    # Add timing information if context was created with timestamp
    if "context_created_at" in context:
        merged_extra["context_duration"] = time.time() - context["context_created_at"]

    rv.__dict__["extra"] = merged_extra
    return rv
