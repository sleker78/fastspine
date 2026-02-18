import asyncio
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Dict, List


@dataclass
class Event:
    """Event class to represent an event with a name and payload."""

    name: str
    payload: dict


class EventDispatcher:
    """Event dispatcher for handling events and their listeners."""

    def __init__(self) -> None:
        self.listeners: Dict[str, List[Callable[..., Any]]] = {}

    def subscribe(self, event_name: str, handler: Callable[..., Any]) -> None:
        """Register a handler for an event."""
        if not callable(handler):
            raise ValueError(f"Handler for {event_name} must be callable")
        if event_name not in self.listeners:
            self.listeners[event_name] = []
        self.listeners[event_name].append(handler)

    async def dispatch(self, event: Event) -> None:
        """Dispatch an event to its listeners."""
        if event.name in self.listeners:
            for handler in self.listeners[event.name]:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event.payload)  # Async handler
                elif hasattr(handler, "delay"):
                    handler.delay(event.payload)  # Celery task
                else:
                    handler(event.payload)  # Regular sync function

    def event_listener(self, event_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register a function as an event listener."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.subscribe(event_name, func)

            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)

            return wrapper

        return decorator


event_dispatcher = EventDispatcher()
