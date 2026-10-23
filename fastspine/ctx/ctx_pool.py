import contextvars
from contextvars import ContextVar
from typing import Any


class CtxPool:
    """A pool for managing context variables."""

    def __init__(self):
        self._vars: dict[str, tuple[ContextVar, bool]] = {}  # map: name -> (ContextVar, persistent: bool)

    def new(self, name: str, default: Any = None, persistant: bool = False) -> ContextVar:
        """Create a new context variable with the given name and default value."""
        var = ContextVar(name, default=default)
        self._vars[name] = (var, persistant)
        return var

    def clear(self):
        """Clear all context variables in the pool."""
        for name, (var, persistent) in self._vars.items():
            if not persistent:
                var.set(None)

    def clear_one(self, name: str, value: Any = None):
        """Clear a specific context variable by name."""
        if name in self._vars:
            var, persistent = self._vars[name]
            if not persistent:
                var.set(value)
            else:
                raise ValueError(f"Cannot clear persistent context variable '{name}'.")
        else:
            raise KeyError(f"Context variable '{name}' not found in the pool.")

    def get(self, name: str, default: Any = None) -> Any:
        """Get the value of a context variable by name."""
        if name in self._vars:
            var, _ = self._vars[name]
            value = var.get()
            if value is not None:
                return value

        return default

    def get_context_var_value[K, V](self, context_var: contextvars.ContextVar[dict[K, V] | None]) -> dict[K, V]:
        """Get the value of a context variable, returning an empty dictionary if it's None."""
        _ctx_var_name = context_var.name
        if _ctx_var_name not in self._vars:
            raise KeyError(f"Context variable '{_ctx_var_name}' not found in the pool.")

        value = context_var.get()

        if value is None:
            return {}
        return value

    def set(self, name: str, value: Any, create: bool = True) -> Any:
        """Set the value of a context variable by name."""
        if name in self._vars:
            var, _ = self._vars[name]
            var.set(value)
            return value
        if create:
            var = self.new(name, default=value)
            var.set(value)
            self._vars[name] = (var, False)
            return value

        raise KeyError(f"Context variable '{name}' not found in the pool.")


# pool instance
ctxpool = CtxPool()
