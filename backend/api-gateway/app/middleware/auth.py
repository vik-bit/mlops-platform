from fastapi import Request
from fastapi.responses import JSONResponse

from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.jwt_handler import verify_token


PUBLIC_PATHS = [
    "/",
    "/docs",
    "/openapi.json",
    "/health",
    "/login"
]


class AuthMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):

        # Always let CORS preflight through — OPTIONS has no auth header
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        if path in PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")

        if not auth_header:

            return JSONResponse(
                status_code=401,
                content={"detail": "Missing token"}
            )

        try:

            token = auth_header.split(" ")[1]

            payload = verify_token(token)

            request.state.user = payload

        except Exception:

            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token"}
            )

        return await call_next(request)