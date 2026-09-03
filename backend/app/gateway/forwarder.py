"""Forward an allowed request to the tenant's upstream and stream the reply back."""
import httpx
from fastapi import Request
from starlette.background import BackgroundTasks
from starlette.responses import Response, StreamingResponse

from app.gateway.client import get_http_client
from app.gateway.http_util import (
    build_upstream_url,
    filter_request_headers,
    filter_response_headers,
)


class UpstreamError(Exception):
    """Upstream unreachable / timed out. Carries the status to return."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


async def forward(
    request: Request,
    *,
    upstream_base: str,
    path: str,
    client_ip: str,
    background: BackgroundTasks,
) -> Response:
    client = get_http_client()
    url = build_upstream_url(upstream_base, path, request.url.query)
    headers = filter_request_headers(
        request.headers.items(),
        client_ip=client_ip,
        forwarded_host=request.headers.get("host"),
    )
    body = await request.body()  # v1: buffer the request body (API payloads are small)

    upstream_req = client.build_request(request.method, url, headers=headers, content=body)
    try:
        upstream_resp = await client.send(upstream_req, stream=True)
    except httpx.TimeoutException as exc:
        raise UpstreamError(504, "Upstream timed out") from exc
    except httpx.HTTPError as exc:
        raise UpstreamError(502, "Upstream unreachable") from exc

    # stream raw bytes straight through; close the upstream connection when done
    background.add_task(upstream_resp.aclose)
    return StreamingResponse(
        upstream_resp.aiter_raw(),
        status_code=upstream_resp.status_code,
        headers=dict(filter_response_headers(upstream_resp.headers.items())),
    )
