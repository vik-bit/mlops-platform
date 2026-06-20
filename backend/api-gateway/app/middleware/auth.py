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

            # split() + IndexError is moved inside the try block — a header
            # like "Bearer" with no token, or one with no space at all,
            # previously raised an uncaught IndexError here (a 500), instead
            # of falling through to the same clean 401 a bad/expired JWT gets.
            scheme, _, token = auth_header.partition(" ")

            if scheme.lower() != "bearer" or not token:
                raise ValueError("Malformed Authorization header")

            payload = verify_token(token)

            request.state.user = payload

        except Exception:

            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token"}
            )

        return await call_next(request)