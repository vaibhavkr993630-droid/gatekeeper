"""Error tracking — strictly opt-in. No-op unless SENTRY_DSN is set, so local
dev and CI never need a Sentry account."""
import logging

from app.core.config import settings

log = logging.getLogger("gatekeeper.sentry")


def init_sentry() -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )
    log.info("Sentry initialized", extra={"environment": settings.environment})
