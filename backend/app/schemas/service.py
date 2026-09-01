from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

from app.core.enums import RateLimitAlgorithm


class RuleIn(BaseModel):
    algorithm: RateLimitAlgorithm
    limit: int = Field(gt=0, le=1_000_000, description="requests allowed per window")
    window_seconds: int = Field(gt=0, le=86_400)
    burst: int | None = Field(default=None, gt=0, le=1_000_000)

    @model_validator(mode="after")
    def _burst_not_below_limit(self) -> "RuleIn":
        if self.burst is not None and self.burst < self.limit:
            raise ValueError("burst must be >= limit")
        return self


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    algorithm: RateLimitAlgorithm
    limit: int
    window_seconds: int
    burst: int | None


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    upstream_url: AnyHttpUrl
    rule: RuleIn


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    upstream_url: AnyHttpUrl | None = None
    is_active: bool | None = None


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: str
    name: str
    upstream_url: str
    is_active: bool
    rule: RuleOut
    created_at: datetime


class ApiKeyCreate(BaseModel):
    name: str | None = Field(default=None, max_length=200)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None
    prefix: str
    last_four: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None


class ApiKeyCreated(ApiKeyOut):
    api_key: str  # plaintext — returned only once, on creation
