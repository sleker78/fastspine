import uuid
from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.types import ASGIApp, Receive, Scope, Send

from faststack.lib.contextualize import contextualize
from faststack.lib.profiler import Profiler

from ..ctx.ctx_pool import ctxpool

request_context: ContextVar = ctxpool.new("request_context", default=None)


class RequestMiddleware(BaseHTTPMiddleware):
    """Middleware for managing the database session per request."""

    async def dispatch(self, request: Request, call_next):
        """Process the request and set up the context for logging and profiling."""
        correlation_id = str(uuid.uuid4())

        request.state.profiler = Profiler()
        ctxpool.set("request_context", request)
        logger_context = {
            "correlation_id": correlation_id,
            "endpoint_path": request.url.path,
            "method": request.method,
        }
        if hasattr(request.state, "user"):
            logger_context["user"] = request.state.user.email
        # Set logger in context and automatically clean up after request
        with contextualize(**logger_context):
            return await call_next(request)


class RequestMiddlewareASGI:
    """Pure ASGI middleware for managing request context and profiling."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle ASGI requests with request context management and profiling."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = str(uuid.uuid4())

        # Create request object to access state
        request = StarletteRequest(scope, receive)
        request.state.profiler = Profiler()
        ctxpool.set("request_context", request)

        logger_context = {
            "correlation_id": correlation_id,
            "endpoint_path": request.url.path,
            "method": request.method,
        }
        if hasattr(request.state, "user"):
            logger_context["user"] = request.state.user.email

        # Set logger in context and automatically clean up after request
        with contextualize(**logger_context):
            await self.app(scope, receive, send)
