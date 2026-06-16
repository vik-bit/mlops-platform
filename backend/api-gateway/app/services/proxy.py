from fastapi import Response
import httpx

# Headers that must not be forwarded — httpx recalculates these
HOP_BY_HOP = {
    "host", "content-length", "transfer-encoding",
    "connection", "keep-alive", "te", "trailers", "upgrade",
}


async def forward_request(
    method: str,
    url: str,
    body=None,
    headers=None,
    params=None,
    content=None,
):
    # Strip hop-by-hop headers so httpx sets Content-Length correctly
    clean_headers = {
        k: v for k, v in (headers or {}).items()
        if k.lower() not in HOP_BY_HOP
    }

    async with httpx.AsyncClient(timeout=200.0) as client:
        response = await client.request(
            method=method,
            url=url,
            json=body,
            content=content,
            headers=clean_headers,
            params=params,
        )

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type"),
        )