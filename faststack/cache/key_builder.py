import hashlib
import json
from typing import Any, Callable, Dict, Tuple

from .cache_model import CachableModel


class KeyBuilder:
    """A class to build cache keys for various entities."""

    @staticmethod
    def hash_key(key: str) -> str:
        """Generates a hash for the given key."""
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def key_builder(
        func: Callable[..., Any],
        namespace: str = "",
        *,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
    ) -> str:
        """Builds a cache key based on the function name, module, and parameters."""
        key_args = args[1:] if args and hasattr(args[0], "__class__") else args
        cache_key = f"{func.__module__}:{func.__name__}:{key_args}:{kwargs}"

        return KeyBuilder.hash_key(f"{namespace}:{cache_key}")

    @staticmethod
    def request_key_builder(
        func: Callable[..., Any],
        version: str = "v1",
        key_prefix: str = "cache",
        params: dict | None = None,
    ) -> str:
        """Builds a cache key for request-based functions."""
        cache_key = f"{version}:{version}:{func.__module__}:{func.__name__}:{json.dumps(params, sort_keys=True)}"
        return KeyBuilder.hash_key(cache_key)

    @staticmethod
    def model_key_builder(model: CachableModel) -> str:
        """Builds a cache key for a CachableModel instance."""
        if not isinstance(model, CachableModel):
            raise TypeError("model must be an instance of CachableModel")

        cache_identifier = model.get_cache_identifier()
        class_name = model.__class__.__name__
        key = f"{class_name}:{cache_identifier}"
        return KeyBuilder.hash_key(key)

    @staticmethod
    def model_plain_key_builder(cls: str, cache_identifier: str) -> str:
        """Builds a plain cache key for a CachableModel instance."""
        if not cache_identifier:
            raise ValueError("identifier must be a non-empty string")

        return KeyBuilder.hash_key(f"{cls}:{cache_identifier}")
