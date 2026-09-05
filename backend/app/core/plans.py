"""Plan tiers as plain config, not a billing system (explicitly out of scope for v1
per the brief). Just enough to let the admin view flag tenants near/over quota."""

PLAN_DAILY_REQUEST_LIMITS: dict[str, int] = {
    "free": 1_000,
    "pro": 50_000,
    "enterprise": 1_000_000,
}
DEFAULT_PLAN_LIMIT = PLAN_DAILY_REQUEST_LIMITS["free"]


def daily_limit_for(plan: str) -> int:
    return PLAN_DAILY_REQUEST_LIMITS.get(plan, DEFAULT_PLAN_LIMIT)
