from fastapi import Response
import httpx


async def forward_request(
    method: str,
    url: str,
    body=None,
    headers=None,
    params=None,
    content=None,
):
    async with httpx.AsyncClient(timeout=30.0) as client:

        response = await client.request(
            method=method,
            url=url,
            json=body,
            content=content,
            headers=headers,
            params=params,
        )

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type"),
        )