import hashlib
import inspect
import io
import json
from enum import Enum
from typing import Any, Callable

import polars as pl
from pydantic import BaseModel

from .cache_model import CachableModel


class KeyBuilder:
    """A class to build cache keys for various entities."""

    @staticmethod
    def hash_key(key: str) -> str:
        """Generates a hash for the given key."""
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def _normalize_for_cache(obj: Any) -> Any:
        """Normalize data structures for consistent cache keys by sorting lists and dicts."""
        if isinstance(obj, pl.DataFrame):
            unsupported = [name for name, dtype in obj.schema.items() if dtype == pl.Object]
            if unsupported:
                raise TypeError(f"Cannot build a cache key: DataFrame has unsupported Object column(s): {unsupported}")

            # Sort elements within List-typed cells first, so two rows differing only by list order
            # (same underlying set) don't produce different bytes - and don't destabilize the row sort
            # below, which would otherwise use those lists as sort keys in their as-given order.
            list_columns = [name for name, dtype in obj.schema.items() if isinstance(dtype, pl.List)]
            if list_columns:
                obj = obj.with_columns([pl.col(c).list.sort() for c in list_columns])

            # write_ipc preserves dtype (unlike to_dict, where e.g. Int32 and Int64 columns with the
            # same values collapse to identical Python ints) and avoids materializing the whole frame
            # into Python objects just to build a key. rechunk() and an explicit (uncompressed)
            # compression setting keep the output bytes tied only to the data, not to
            # implementation details (chunk layout, default codec) that could change between
            # polars versions and silently invalidate the cache.
            df = obj.select(sorted(obj.columns)).sort(pl.all()).rechunk()
            buf = io.BytesIO()
            df.write_ipc(buf, compression="uncompressed")
            return hashlib.sha256(buf.getvalue()).hexdigest()

        if isinstance(obj, dict):
            try:
                items = sorted(obj.items())
            except TypeError:
                # Keys aren't mutually comparable (e.g. mixed int/str keys) - fall back to sorting
                # by repr so this stays deterministic instead of raising a raw, unhelpful TypeError.
                items = sorted(obj.items(), key=lambda kv: repr(kv[0]))
            return {k: KeyBuilder._normalize_for_cache(v) for k, v in items}

        if isinstance(obj, (list, tuple, set, frozenset)):
            # Sort for consistent ordering. Sets in particular have no defined iteration order -
            # it depends on PYTHONHASHSEED, which differs per worker process, so an unsorted set
            # would produce a different cache key for the same logical input across workers.
            try:
                return sorted([KeyBuilder._normalize_for_cache(item) for item in obj])
            except TypeError:
                # If items are not sortable, use repr (not str) so e.g. None and "None", or 1 and
                # "1", don't collide into the same cache key.
                return sorted([repr(KeyBuilder._normalize_for_cache(item)) for item in obj])

        if isinstance(obj, BaseModel):
            return KeyBuilder._normalize_for_cache(obj.model_dump())

        if isinstance(obj, Enum):
            return f"{type(obj).__name__}.{obj.name}"

        if hasattr(obj, "__dict__"):
            raise TypeError(
                f"Cannot build a cache key for unsupported type: {type(obj)!r}. "
                "Use a Pydantic model, an Enum, or implement CachableModel."
            )

        return obj

    @staticmethod
    def key_builder(
        func: Callable[..., Any],
        namespace: str = "",
        *,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> str:
        """Builds a cache key based on the function name, module, and parameters."""
        sig_params = list(inspect.signature(func).parameters)
        is_bound_method = bool(sig_params) and sig_params[0] in ("self", "cls")
        key_args = args[1:] if is_bound_method and args else args

        # Normalize args for deterministic serialization (sort lists and dicts)
        normalized_args = KeyBuilder._normalize_for_cache(key_args)

        # Normalize kwargs for deterministic serialization (sort lists and dicts)
        normalized_kwargs = KeyBuilder._normalize_for_cache(kwargs)

        cache_key = f"{func.__module__}:{func.__name__}:{normalized_args}:{normalized_kwargs}"

        return KeyBuilder.hash_key(f"{namespace}:{cache_key}")

    @staticmethod
    def request_key_builder(
        func: Callable[..., Any],
        version: str = "v1",
        key_prefix: str = "cache",
        params: dict | None = None,
    ) -> str:
        """Builds a cache key for request-based functions."""
        normalized_params = KeyBuilder._normalize_for_cache(params)
        cache_key = f"{key_prefix}:{version}:{func.__module__}:{func.__name__}:{json.dumps(normalized_params)}"
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
