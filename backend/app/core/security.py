import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

API_KEY_PREFIX = "gk_"

# bcrypt operates on at most 72 bytes; longer inputs are pre-hashed by callers
# elsewhere only if needed. Pydantic already caps password length at 128 chars.
_BCRYPT_MAX_BYTES = 72


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode()[:_BCRYPT_MAX_BYTES], bcrypt.gensalt()).decode()


def verify_password(raw: str, hashed: str) -> bool:
    return bcrypt.checkpw(raw.encode()[:_BCRYPT_MAX_BYTES], hashed.encode())


def create_access_token(*, user_id: int, tenant_id: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "tid": tenant_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    """Raises JWTError on any invalid/expired token."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


# --- Platform admin tokens ---------------------------------------------------
# Deliberately signed with a *different* secret than tenant tokens. This isn't
# just "a different claim to check" — an admin token is cryptographically
# unforgeable from a tenant token, and vice versa, even if one secret leaks.


def create_admin_token(*, admin_id: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(admin_id),
        "scope": "admin",
        "iat": now,
        "exp": now + timedelta(minutes=settings.admin_access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.admin_secret_key, algorithm=settings.algorithm)


def decode_admin_token(token: str) -> dict:
    """Raises JWTError on any invalid/expired token."""
    return jwt.decode(token, settings.admin_secret_key, algorithms=[settings.algorithm])


# --- Gateway API keys -------------------------------------------------------
# Distinct from JWT: long-lived, machine-to-machine, scoped to one service.
# We store only a SHA-256 hash + a display hint; the plaintext is shown once.


@dataclass(frozen=True)
class GeneratedApiKey:
    plaintext: str
    key_hash: str
    prefix: str  # e.g. "gk_a1b2c3d4" — safe to display/index
    last_four: str


def hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def generate_api_key() -> GeneratedApiKey:
    secret = secrets.token_urlsafe(32)
    plaintext = f"{API_KEY_PREFIX}{secret}"
    return GeneratedApiKey(
        plaintext=plaintext,
        key_hash=hash_api_key(plaintext),
        prefix=plaintext[: len(API_KEY_PREFIX) + 8],
        last_four=plaintext[-4:],
    )


__all__ = [
    "API_KEY_PREFIX",
    "GeneratedApiKey",
    "JWTError",
    "create_access_token",
    "create_admin_token",
    "decode_access_token",
    "decode_admin_token",
    "generate_api_key",
    "hash_api_key",
    "hash_password",
    "verify_password",
]
