from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.proxy import forward_request


router = APIRouter()


SERVICES = {
    "datasets":   "http://dataset-service:8000",
    "training":   "http://training-service:8000",
    "deployment": "http://deployment-service:8000",
    "monitoring": "http://monitoring-service:8000",
}

# Routes accessible to all authenticated users (non-admin)
USER_ALLOWED = {
    "datasets":   {"GET", "POST", "DELETE"},       # upload, list, delete own datasets
    "deployment": {"GET", "POST"},                  # list deployments, predict, explain
}

# Admin-only services
ADMIN_ONLY = {"training", "monitoring"}


@router.api_route(
    "/api/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE"]
)
async def gateway_proxy(service: str, path: str, request: Request):

    if service not in SERVICES:
        return JSONResponse(status_code=404, content={"detail": "Service not found"})

    user = request.state.user
    role = user.get("role")

    # Admin-only services
    if service in ADMIN_ONLY and role != "admin":
        return JSONResponse(status_code=403, content={"detail": "Admin access required"})

    # Non-admin users: check method allowlist
    if role != "admin" and service in USER_ALLOWED:
        if request.method not in USER_ALLOWED[service]:
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    target_url = f"{SERVICES[service]}/{path}"
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        response = await forward_request(
            method=request.method,
            url=target_url,
            content=await request.body(),
            headers=dict(request.headers),
            params=dict(request.query_params),
        )
    else:
        body = None
        try:
            body = await request.json()
        except Exception:
            pass
        response = await forward_request(
            method=request.method,
            url=target_url,
            body=body,
            headers=dict(request.headers),
            params=dict(request.query_params),
        )

    return response