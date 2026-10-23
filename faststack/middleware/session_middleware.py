from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from ..ctx.ctx_pool import ctxpool
from ..dependencies.repository_manager import _close_sessions


class DBSessionMiddleware(BaseHTTPMiddleware):
    """Middleware for managing the database session per request."""

    async def dispatch(self, request: Request, call_next):
        """Dispatch method for the middleware."""
        try:
            return await call_next(request)  # Process request
        finally:
            await _close_sessions()
            ctxpool.clear()


class DBSessionMiddlewareASGI:
    """Pure ASGI middleware for managing database sessions per request."""

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the ASGI middleware with the application."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle ASGI requests with database session management."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        try:
            await self.app(scope, receive, send)
        finally:
            await _close_sessions()
            ctxpool.clear()
