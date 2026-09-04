from pydantic import BaseModel

from app.schemas.service import RuleOut


class StatPoint(BaseModel):
    minute: str
    requests: int
    blocked: int


class StatTotals(BaseModel):
    requests: int
    blocked: int
    block_rate: float


class ServiceStats(BaseModel):
    service_id: int
    window_minutes: int
    rule: RuleOut
    totals: StatTotals
    series: list[StatPoint]
