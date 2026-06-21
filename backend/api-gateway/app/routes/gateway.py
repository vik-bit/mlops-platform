import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.proxy import forward_request


router = APIRouter()


# Reads the real Render URL from each *_SERVICE_URL env var (set in
# render.yaml as https://mlops-<service>.onrender.com). Falls back to the
# Docker Compose hostname only if the env var is unset, so local
# `docker compose up` still works with zero configuration.
#
# CONFIRMED LIVE BUG (June 21): the version actually deployed to Render
# had these as bare hardcoded strings — "http://training-service:8000" —
# with no os.environ.get() at all. That hostname does not exist outside
# a Docker Compose network, so every proxied request failed with
# httpx.ConnectError: [Errno -2] Name or service not known, which Starlette
# then turned into a bare 500 with no CORS headers, which the browser
# reported as a CORS policy violation even though CORS was never the
# actual problem. After deploying THIS file, verify in the gateway's logs
# that target_url for a test request shows an https://...onrender.com
# address, not a bare service-name:port string.
SERVICES = {
    "datasets":   os.environ.get("DATASET_SERVICE_URL",   "http://dataset-service:8000"),
    "training":   os.environ.get("TRAINING_SERVICE_URL",  "http://training-service:8000"),
    "deployment": os.environ.get("DEPLOYMENT_SERVICE_URL","http://deployment-service:8000"),
    "monitoring": os.environ.get("MONITORING_SERVICE_URL","http://monitoring-service:8000"),
    "copilot":    os.environ.get("AI_SERVICE_URL",        "http://ai-service:8000"),
}

# Routes accessible to all authenticated users (non-admin)
USER_ALLOWED = {
    "datasets":   {"GET", "POST", "DELETE"},       # upload, list, delete own datasets
    "deployment": {"GET", "POST"},                  # list deployments, predict, explain
    "copilot":    {"GET", "POST"},                  # chat, explain, compare — all users
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