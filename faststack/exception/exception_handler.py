from fastapi import Request
from fastapi.responses import JSONResponse

from .base_app_exception import BaseAppError


async def value_error_handler(request: Request, exc: BaseAppError) -> JSONResponse:
    """Handle BaseAppError exceptions."""
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})
