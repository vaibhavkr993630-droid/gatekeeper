from enum import StrEnum


class RateLimitAlgorithm(StrEnum):
    """Pluggable algorithms. Implementations land in `app/rate_limit/` in Phase 3;
    the enum lives here so models/schemas can reference it without importing that layer.
    """

    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW_COUNTER = "sliding_window_counter"
