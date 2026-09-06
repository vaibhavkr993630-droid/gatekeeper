"""Structured logging.

Demo/dev default is plain text (readable in a terminal); set `LOG_JSON=true`
(the container/production default — see docker-compose.yml) for one JSON object
per line, the shape a log aggregator (CloudWatch, Loki, Datadog, ...) expects.
Every line — ours and uvicorn's — carries the same `request_id` via
`RequestIdLogFilter` so one request's logs can be pulled out with a single filter.
"""
import json
import logging
import sys
from datetime import UTC, datetime

from app.core.config import settings
from app.core.request_context import RequestIdLogFilter

# Attributes every LogRecord already has — anything else on the record is a field
# a caller passed via `logger.info(..., extra={...})` and belongs in the output.
_STANDARD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and key != "request_id":
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_PLAIN_FORMAT = "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s"


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if settings.log_json else logging.Formatter(_PLAIN_FORMAT))
    handler.addFilter(RequestIdLogFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)

    # route the noisy third-party loggers through the same handler instead of
    # letting uvicorn install its own colored formatter alongside ours
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
