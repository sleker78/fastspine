import contextvars

_cache_enabled_var: contextvars.ContextVar[bool | None] = contextvars.ContextVar("_cache_enabled_var", default=None)


class CacheSettings:
    """Settings class for cache configuration."""

    REDIS_USER: str = ""
    REDIS_PASSWORD: str = ""
    REDIS_PORT: int = 6397
    REDIS_HOST: str = "localhost"
    CACHE_ENABLED: bool = True
    CACHE_KEY_PREFIX: str | None = None
    CACHED_DISABLED_USERS: list[str] = []

    def get_url(self):
        """Construct the Redis URL from the settings."""
        return f"redis://{self.REDIS_USER}:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}"

    @property
    def is_cache_enabled(self) -> bool:
        """Check if caching is enabled for the current request context.

        Falls back to the global CACHE_ENABLED setting when no request has set a context-specific value.
        """
        value = _cache_enabled_var.get()
        return value if value is not None else self.CACHE_ENABLED

    def set_cache_enabled(self, user_email: str):
        """Set cache state for the current request context based on global setting and user-specific rules."""
        _cache_enabled_var.set(self.CACHE_ENABLED and user_email not in self.CACHED_DISABLED_USERS)
