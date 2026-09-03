"""Pure helpers for the proxy path — no I/O, unit-tested directly."""
from collections.abc import Iterable, Mapping
from urllib.parse import urljoin, urlsplit, urlunsplit

# RFC 7230 hop-by-hop headers plus a few the proxy must own itself. Never forwarded
# in either direction.
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",
    }
)
# Credentials the gateway consumed; the tenant's own backend must not see them.
_STRIP_TO_UPSTREAM = frozenset({"authorization", "x-api-key"})


def build_upstream_url(base: str, path: str, query: str) -> str:
    """Join the service's `upstream_url` with the captured trailing path + query.

    `base` may or may not have a trailing path component; `path` is what followed
    `/gw/{public_id}/`. A path of "" forwards to the base itself.
    """
    scheme, netloc, base_path, _, _ = urlsplit(base)
    if not base_path.endswith("/"):
        base_path += "/"
    merged = urljoin(base_path, path.lstrip("/"))
    return urlunsplit((scheme, netloc, merged, query, ""))


def filter_request_headers(
    headers: Iterable[tuple[str, str]], *, client_ip: str, forwarded_host: str | None
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen_xff = False
    for key, value in headers:
        low = key.lower()
        if low in _HOP_BY_HOP or low in _STRIP_TO_UPSTREAM:
            continue
        if low == "x-forwarded-for":
            out.append((key, f"{value}, {client_ip}"))
            seen_xff = True
            continue
        out.append((key, value))
    if not seen_xff:
        out.append(("x-forwarded-for", client_ip))
    if forwarded_host:
        out.append(("x-forwarded-host", forwarded_host))
    return out


def filter_response_headers(
    headers: Iterable[tuple[str, str]],
) -> list[tuple[str, str]]:
    # keep content-length / content-encoding: we stream raw bytes and don't re-encode
    drop = _HOP_BY_HOP - {"content-length"}
    return [(k, v) for k, v in headers if k.lower() not in drop]


def extract_api_key(headers: Mapping[str, str]) -> str | None:
    """`Authorization: Bearer gk_...` or `X-API-Key: gk_...`."""
    auth = headers.get("authorization") or headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return (headers.get("x-api-key") or headers.get("X-API-Key") or "").strip() or None


def client_ip_from(*, forwarded_for: str | None, peer: str | None, trust_forwarded: bool) -> str:
    if trust_forwarded and forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return peer or "unknown"
