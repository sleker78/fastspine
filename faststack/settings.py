import types
from functools import lru_cache
from typing import Union, get_args, get_origin

from pydantic_settings import BaseSettings

from .ctx.ctx_pool import ctxpool
from .mixins.representable import RepresentableMixin

CORE_SETTINGS_CTX_NAME = "core_settings_ctx"
core_settings_ctx = ctxpool.new(CORE_SETTINGS_CTX_NAME, persistant=True)


class CelerySettings:
    """Settings class for Celery configuration."""

    CELERY_RESULT_EXPIRES: int = 7 * 24 * 60 * 60  # 7 days
    CELERY_BROKER_URI: str = ""
    CELERY_BACKEND_URI: str = "redis://localhost:6385/0"
    CELERY_MAIN_NAME: str = "_redis_main"
    CELERY_TASK_FOLDERS: list[str] = []
    WORKERS_ON: bool = True  # Whether workers are enabled
    VISIBILITY_TIMEOUT: int = 3600  # Default visibility timeout for tasks in seconds


class AppSettings:
    """Settings class for application configuration."""

    DEBUG_MODE: bool = False
    PROJECT_NAME: str = "FastStackLib Application::Change me in production"


class CacheSettings:
    """Settings class for cache configuration."""

    CACHE_KEY_PREFIX: str = "_cache_"
    CACHE_ENABLED: bool = True


class MailerSettings:
    """Settings class for mailer configuration."""

    MAIL_USERNAME: str | None = None
    MAIL_PASSWORD: str | None = None
    MAIL_FROM: str | None = None
    MAIL_PORT: int | None = None
    MAIL_SERVER: str | None = None
    MAIL_STARTTLS: bool | None = None
    MAIL_SSL_TLS: bool | None = None
    USE_CREDENTIALS: bool | None = None
    VALIDATE_CERTS: bool | None = None


class CoreSettings(AppSettings, CacheSettings, CelerySettings, MailerSettings, RepresentableMixin):
    """Settings class for core application settings and secrets management."""

    def __init__(self, settings: BaseSettings | None = None):
        """Initialize the CoreSettings with optional BaseSettings."""
        if settings:
            self._set_properties(settings)

    @staticmethod
    def is_optional_type(annotation) -> bool:
        """Check if the annotation is an optional type."""
        # Handle new Union syntax (T | None) from Python 3.10+
        if isinstance(annotation, types.UnionType):
            return type(None) in annotation.__args__

        # Handle old Union syntax (Union[T, None])
        return get_origin(annotation) is Union and type(None) in get_args(annotation)

    def _set_properties(self, settings: BaseSettings):
        from typing import get_type_hints

        type_hints = get_type_hints(self.__class__)

        for key, annotation in type_hints.items():
            is_optional = self.is_optional_type(annotation)
            if not hasattr(settings, key):
                if not is_optional:
                    raise RuntimeError(f"Missing required setting: {key}")
                continue

            value = getattr(settings, key, None)

            if value is None and not is_optional:
                raise RuntimeError(f"Setting '{key}' cannot be None (not Optional)")

            setattr(self, key, value)


def init_core_settings(settings: BaseSettings | None = None) -> CoreSettings:
    """Initialize the core settings."""
    core_settings = CoreSettings(settings=settings)

    ctxpool.set(CORE_SETTINGS_CTX_NAME, core_settings)
    return core_settings


@lru_cache
def get_core_settings() -> CoreSettings:
    """Get the core settings."""
    _core_settings = ctxpool.get(CORE_SETTINGS_CTX_NAME)

    if _core_settings is None:
        raise RuntimeError("CoreSettings is not initialized")
    return _core_settings
