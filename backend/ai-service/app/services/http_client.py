import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None
_lock = asyncio.Lock()


def _build_transport() -> httpx.AsyncHTTPTransport:
    return httpx.AsyncHTTPTransport(
        retries=3,                 # auto-retry on connect-stage failures
        local_address="0.0.0.0",   # force IPv4 — this env has no IPv6 route
    )


def _build_limits() -> httpx.Limits:
    return httpx.Limits(
        max_connections=20,
        max_keepalive_connections=5,
        keepalive_expiry=15.0,     # YOUR client retires idle sockets before
                                    # Groq/Cloudflare's edge does it for you
    )


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        async with _lock:
            if _client is None or _client.is_closed:
                _client = httpx.AsyncClient(
                    transport=_build_transport(),
                    limits=_build_limits(),
                    timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
                    http2=False,
                )
                logger.info("HTTP client (re)initialized")
    return _client


async def close_client():
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None