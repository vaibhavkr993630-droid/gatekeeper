"""Rate-limiter pieces that need neither Redis nor a DB."""
import pytest

from app.core.enums import RateLimitAlgorithm
from app.models.service import RateLimitRule
from app.rate_limit import SlidingWindowCounterLimiter, TokenBucketLimiter, make_key
from app.rate_limit.factory import get_rate_limiter


def test_make_key_uses_cluster_hash_tag():
    assert make_key("svc_abc", "203.0.113.7") == "rl:{svc_abc}:203.0.113.7"


def test_factory_maps_token_bucket_params():
    rule = RateLimitRule(
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET, limit=120, window_seconds=60, burst=200
    )
    limiter = get_rate_limiter(rule, redis=None)
    assert isinstance(limiter, TokenBucketLimiter)
    assert limiter.capacity == 200
    assert limiter.rate == pytest.approx(2.0)  # 120 / 60s


def test_factory_maps_sliding_window_params():
    rule = RateLimitRule(
        algorithm=RateLimitAlgorithm.SLIDING_WINDOW_COUNTER,
        limit=50,
        window_seconds=10,
        burst=None,
    )
    limiter = get_rate_limiter(rule, redis=None)
    assert isinstance(limiter, SlidingWindowCounterLimiter)
    assert (limiter.limit, limiter.window_seconds) == (50, 10)


def test_factory_rejects_unknown_algorithm():
    rule = RateLimitRule(algorithm="leaky_bucket", limit=1, window_seconds=1, burst=None)
    with pytest.raises(ValueError, match="unknown rate-limit algorithm"):
        get_rate_limiter(rule, redis=None)


@pytest.mark.parametrize(
    "kwargs",
    [{"rate": 0, "capacity": 10}, {"rate": 1, "capacity": 0}],
)
def test_token_bucket_rejects_bad_config(kwargs):
    with pytest.raises(ValueError):
        TokenBucketLimiter(redis=None, **kwargs)
