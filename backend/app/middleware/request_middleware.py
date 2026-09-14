from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.core.logger import setup_logging


ASGIApp = Callable[[dict[str, Any], Callable[..., Awaitable[None]], Callable[..., Awaitable[None]]], Awaitable[None]]


class RequestMiddleware:
    """Add request tracing headers and log the outcome of each request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        # Use the application's shared logger so middleware logs follow the
        # same configuration as startup and shutdown logs.
        self.logger = setup_logging()

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[None]],
        send: Callable[..., Awaitable[None]],
    ) -> None:
        # Only HTTP requests have the method, path, and response headers this
        # middleware is responsible for tracking.
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # Create one identifier and one high-resolution timer for this request.
        request_id = str(uuid4())
        started_at = perf_counter()
        status_code = 500
        process_time = 0.0

        async def send_with_headers(message: dict[str, Any]) -> None:
            nonlocal status_code, process_time

            # Add tracing headers when the response begins, before its headers
            # are sent to the client.
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 500))
                process_time = perf_counter() - started_at
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-request-id", request_id.encode("ascii")),
                        (b"x-process-time", f"{process_time:.6f}".encode("ascii")),
                    ]
                )
                message["headers"] = headers

            await send(message)

        try:
            # Forward the request while intercepting the response start event.
            await self.app(scope, receive, send_with_headers)
        finally:
            # Log successful responses and exceptions using the same measured
            # duration that was exposed to the client.
            process_time = process_time or perf_counter() - started_at
            self.logger.info(
                "%s %s %s %.6fs",
                scope.get("method", "UNKNOWN"),
                scope.get("path", ""),
                status_code,
                process_time,
            )