"""SSRF guard for tenant-supplied `upstream_url`.

Without this, a tenant could point their service at `http://169.254.169.254/`
(a cloud metadata endpoint), `http://localhost:5432`, or an internal `10.x`
address, and use GateKeeper as an authenticated proxy into infrastructure they
shouldn't be able to reach. Gated behind `settings.block_private_upstreams`
(see config.py for why it defaults off).

This is a best-effort check, not a complete SSRF defense: it validates at
service-creation time, so a DNS record that later repoints to a private address
("DNS rebinding") would slip through. A production deployment would also pin
the resolved IP at connection time (e.g. via a custom httpx transport) rather
than trusting a one-time hostname check.
"""
import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeUpstreamError(ValueError):
    pass


def _is_non_routable(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def assert_public_upstream(url: str) -> None:
    """Raises `UnsafeUpstreamError` if `url`'s host is not a public address."""
    host = urlsplit(url).hostname
    if not host:
        raise UnsafeUpstreamError("URL has no host")
    if host.lower() == "localhost":
        raise UnsafeUpstreamError("localhost is not a routable upstream")

    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if _is_non_routable(literal_ip):
            raise UnsafeUpstreamError(f"{host} is a non-routable address")
        return

    try:
        resolved = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeUpstreamError(f"could not resolve host {host!r}") from exc
    for family_info in resolved:
        ip = ipaddress.ip_address(family_info[4][0])
        if _is_non_routable(ip):
            raise UnsafeUpstreamError(f"{host} resolves to a non-routable address ({ip})")
