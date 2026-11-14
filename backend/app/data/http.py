"""Shared async HTTP client configured with certifi TLS trust and bounded retries."""

import asyncio
import ssl
import certifi
import httpx


DEFAULT_HEADERS = {
    "User-Agent": "KurinjiKumaraN-SPHEREx/0.1 (NASA-Space-Apps-2026)",
}


def build_ssl_context() -> ssl.SSLContext:
    """Return SSL context backed by certifi CA bundle (fixes Windows intermediate CA gaps)."""
    return ssl.create_default_context(cafile=certifi.where())


def create_async_client(timeout_s: float = 30.0) -> httpx.AsyncClient:
    """Create a pooled httpx AsyncClient safe for Windows/Linux containers."""
    limits = httpx.Limits(max_connections=24, max_keepalive_connections=12)
    timeout = httpx.Timeout(timeout=timeout_s, connect=15.0)
    return httpx.AsyncClient(
        verify=build_ssl_context(),
        headers=DEFAULT_HEADERS,
        limits=limits,
        timeout=timeout,
        follow_redirects=True,
    )


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    max_attempts: int = 3,
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504),
) -> httpx.Response:
    """Issue HTTP request with exponential backoff on transient transport or gateway errors."""
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            resp = await client.request(method, url, headers=headers, params=params)
            if resp.status_code in retry_statuses and attempt < max_attempts - 1:
                await asyncio.sleep(0.5 * (2**attempt))
                continue
            resp.raise_for_status()
            return resp
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in retry_statuses:
                raise
            if attempt < max_attempts - 1:
                await asyncio.sleep(0.5 * (2**attempt))
            else:
                raise
    assert last_exc is not None
    raise last_exc
