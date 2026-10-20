import logging


class ProfilerSettings:
    """Settings class for mailer configuration."""

    PROFILER_NAME: str | None = None
    PROFILER_ENABLED: bool | None = False
    PROFILER_LOG_LEVEL: int = logging.INFO
    PROFILER_TRACK_MEMORY: bool | None = False
