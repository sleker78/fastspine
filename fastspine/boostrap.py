from fastapi import FastAPI
from pydantic_settings import BaseSettings
from starlette.middleware.base import BaseHTTPMiddleware

from .exception.base_app_exception import BaseAppError
from .exception.exception_handler import value_error_handler
from .settings import CoreSettings, init_core_settings


class FastSpineApp(FastAPI):
    """A FastAPI application with core settings and middleware."""

    def __init__(
        self,
        *,
        settings: BaseSettings | None = None,
        use_asgi_middleware: bool = False,
        **kwargs,
    ):
        """Initialize the FastCoreApp with optional settings and middleware choice.

        Accepts every keyword argument `FastAPI.__init__` accepts (`title`, `debug`,
        `lifespan`, ...), forwarded as-is, in addition to `settings` and `use_asgi_middleware`.
        """
        self.core_settings: CoreSettings = init_core_settings(settings=settings)
        kwargs.setdefault("title", self.core_settings.PROJECT_NAME)
        super().__init__(**kwargs)
        self.add_exception_handler(BaseAppError, value_error_handler)

        if use_asgi_middleware:
            from .middleware.request_middleware import RequestMiddlewareASGI as RequestMiddleware
            from .middleware.session_middleware import DBSessionMiddlewareASGI as DBSessionMiddleware
        else:
            from .middleware.request_middleware import RequestMiddleware
            from .middleware.session_middleware import DBSessionMiddleware

        self.add_middleware(RequestMiddleware)
        self.add_middleware(DBSessionMiddleware)

        if self.core_settings.DEBUG_MODE and use_asgi_middleware:
            for m in self.user_middleware:
                if issubclass(m.cls, BaseHTTPMiddleware):
                    raise RuntimeError(
                        f"BaseHTTPMiddleware {m.cls.__name__} is not compatible with streaming mode. Please use the ASGI middleware variants for streaming responses."
                    )


def run_fast_core_app(settings: BaseSettings | None = None, use_asgi_middleware: bool = False) -> FastAPI:
    """Initialize the FastAPI core application.

    Args:
        settings (BaseSettings): The settings instance containing configuration.
        use_asgi_middleware (bool): Whether to use ASGI middleware for streaming responses.

    This function sets up the core settings, middleware, and routes for the FastAPI application.
    """
    core_settings: CoreSettings = init_core_settings(settings=settings)
    app = FastAPI(title=core_settings.PROJECT_NAME)
    app.add_exception_handler(BaseAppError, value_error_handler)

    if use_asgi_middleware:
        from .middleware.request_middleware import RequestMiddlewareASGI as RequestMiddleware
        from .middleware.session_middleware import DBSessionMiddlewareASGI as DBSessionMiddleware
    else:
        from .middleware.request_middleware import RequestMiddleware
        from .middleware.session_middleware import DBSessionMiddleware

    app.add_middleware(RequestMiddleware)
    app.add_middleware(DBSessionMiddleware)

    if core_settings.DEBUG_MODE and use_asgi_middleware:
        for m in app.user_middleware:
            if issubclass(m.cls, BaseHTTPMiddleware):
                raise RuntimeError(
                    f"BaseHTTPMiddleware {m.cls.__name__} is not compatible with streaming mode. Please use the ASGI middleware variants for streaming responses."
                )

    return app
