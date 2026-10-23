import types
from functools import lru_cache
from typing import Union, get_args, get_origin

from pydantic_settings import BaseSettings

from ..ctx.ctx_pool import ctxpool
from ..mixins.representable import RepresentableMixin
from .app_settings import AppSettings
from .cache_settings import CacheSettings
from .celery_settings import CelerySettings
from .mailer_settings import MailerSettings
from .profiler_settings import ProfilerSettings

__all__ = ["CoreSettings", "init_core_settings", "get_core_settings"]

CORE_SETTINGS_CTX_NAME = "core_settings_ctx"
core_settings_ctx = ctxpool.new(CORE_SETTINGS_CTX_NAME, persistant=True)


class CoreSettings(AppSettings, CacheSettings, CelerySettings, MailerSettings, ProfilerSettings, RepresentableMixin):
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
