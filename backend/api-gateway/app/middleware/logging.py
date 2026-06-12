import time

from starlette.middleware.base import BaseHTTPMiddleware


class LoggingMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request, call_next):

        start_time = time.time()

        response = await call_next(request)

        process_time = round(
            (time.time() - start_time) * 1000,
            2
        )

        print(
            f"{request.method} "
            f"{request.url.path} "
            f"Status={response.status_code} "
            f"Latency={process_time}ms"
        )

        response.headers["X-Process-Time"] = str(process_time)

        return response