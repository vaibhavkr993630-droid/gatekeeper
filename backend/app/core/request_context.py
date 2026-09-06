"""Per-request correlation id, threaded through logs and returned to the caller.

Any log line emitted while handling a request carries the same `request_id` as
the `X-Request-ID` response header, so a report like "my call at 10:02 failed"
turns into a single `grep` across structured logs.
"""
import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

_NO_REQUEST = "-"
request_id_var: ContextVar[str] = ContextVar("request_id", default=_NO_REQUEST)


class RequestIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get("x-request-id")
        request_id = incoming if incoming else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestIdLogFilter(logging.Filter):
    """Attaches the current request id to every log record, `-` outside a request."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True
