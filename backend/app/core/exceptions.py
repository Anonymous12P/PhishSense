import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger("phishsense")


def _error_response(code: str, message: str, status_code: int, **kwargs: Any) -> JSONResponse:
    """Build the consistent error envelope used by every exception handler."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
            },
        },
        **kwargs,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return client-safe details for expected HTTP errors."""
    message = str(exc.detail)
    return _error_response(
        code=f"http_{exc.status_code}",
        message=message,
        status_code=exc.status_code,
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return a stable response when request data fails validation."""
    return _error_response(
        code="validation_error",
        message="Request validation failed.",
        status_code=422,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log unexpected failures while returning a non-sensitive error response."""
    logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
    return _error_response(
        code="internal_server_error",
        message="An unexpected error occurred.",
        status_code=500,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the application's consistent exception response handlers."""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)