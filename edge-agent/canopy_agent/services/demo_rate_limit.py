import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Single-process, in-memory fixed-window limiter — matches the same approach and
# trade-offs as canopy-website's rateLimit.ts (one container, no horizontal scaling
# for the demo instance; resets on restart, which is fine for what this exists to
# stop: scripted abuse of a publicly writable demo, not a bulletproof distributed
# limiter). Only ever mounted when CANOPY_DEMO_MODE is on — see main.py.
DEMO_RATE_LIMIT = 60
DEMO_RATE_WINDOW_SECONDS = 60


class _Bucket:
    __slots__ = ("count", "reset_at")

    def __init__(self, reset_at: float) -> None:
        self.count = 1
        self.reset_at = reset_at


class DemoRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = DEMO_RATE_LIMIT, window_seconds: float = DEMO_RATE_WINDOW_SECONDS) -> None:
        super().__init__(app)
        self._limit = limit
        self._window = window_seconds
        self._buckets: dict[str, _Bucket] = {}

    async def dispatch(self, request: Request, call_next):
        key = _client_ip(request)
        now = time.monotonic()
        bucket = self._buckets.get(key)

        if bucket is None or bucket.reset_at <= now:
            self._buckets[key] = _Bucket(now + self._window)
        elif bucket.count >= self._limit:
            retry_after = round(bucket.reset_at - now)
            return JSONResponse(
                {"detail": "rate limit exceeded on this public demo instance"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        else:
            bucket.count += 1

        return await call_next(request)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
