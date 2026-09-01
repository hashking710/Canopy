import os
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Single-process, in-memory fixed-window limiter — same shape and trade-offs as
# services/demo_rate_limit.py (one container, no horizontal scaling; resets on
# restart). Unlike that one, this is always mounted (see main.py), not just in demo
# mode: the real product's API had no rate limiting at all outside the demo
# instance, a real gap for any deployment reachable beyond a pure LAN (the TLS/
# reverse-proxy path in docs/deployment-tls.md exists specifically for that case).
#
# Two tiers, not one:
#   - A generous general limit (CANOPY_RATE_LIMIT_PER_MINUTE, default 120/min per
#     IP) — high enough that normal dashboard usage (page loads, occasional CRUD;
#     live readings come over the WS connection, not HTTP polling) never brushes
#     against it, but still a real ceiling against scripted abuse.
#   - A much stricter throttle on repeated auth failures specifically
#     (CANOPY_AUTH_FAILURE_LIMIT, default 10 per CANOPY_AUTH_FAILURE_WINDOW_SECONDS,
#     default 300s) — once an IP crosses this, every request from it is rejected
#     for the rest of that window regardless of whether a later attempt finally
#     presents the correct token, which is the actual point: slowing a brute-force
#     sweep through token guesses, not just capping request volume.
GENERAL_RATE_LIMIT = int(os.environ.get("CANOPY_RATE_LIMIT_PER_MINUTE", "120"))
GENERAL_RATE_WINDOW_SECONDS = 60
AUTH_FAILURE_LIMIT = int(os.environ.get("CANOPY_AUTH_FAILURE_LIMIT", "10"))
AUTH_FAILURE_WINDOW_SECONDS = int(os.environ.get("CANOPY_AUTH_FAILURE_WINDOW_SECONDS", "300"))


class _Bucket:
    __slots__ = ("count", "reset_at")

    def __init__(self, reset_at: float) -> None:
        self.count = 1
        self.reset_at = reset_at


class _FixedWindowLimiter:
    """Extracted so both tiers below share the exact same bucket logic rather than
    two near-identical copies — see decode_ble_value/scan_for_nearby_devices-style
    split elsewhere in this codebase for the same "shared logic, separate call
    sites" reasoning."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        self._limit = limit
        self._window = window_seconds
        self._buckets: dict[str, _Bucket] = {}

    def hit(self, key: str) -> tuple[bool, float]:
        """Records one hit for `key`. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        bucket = self._buckets.get(key)
        if bucket is None or bucket.reset_at <= now:
            self._buckets[key] = _Bucket(now + self._window)
            return True, 0.0
        if bucket.count >= self._limit:
            return False, round(bucket.reset_at - now)
        bucket.count += 1
        return True, 0.0

    def is_blocked(self, key: str) -> tuple[bool, float]:
        """Read-only check — does not itself count as a hit. Used before call_next
        so an already-throttled IP is rejected without even reaching the route."""
        now = time.monotonic()
        bucket = self._buckets.get(key)
        if bucket is None or bucket.reset_at <= now:
            return False, 0.0
        if bucket.count >= self._limit:
            return True, round(bucket.reset_at - now)
        return False, 0.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        general_limit: int = GENERAL_RATE_LIMIT,
        general_window_seconds: float = GENERAL_RATE_WINDOW_SECONDS,
        auth_failure_limit: int = AUTH_FAILURE_LIMIT,
        auth_failure_window_seconds: float = AUTH_FAILURE_WINDOW_SECONDS,
    ) -> None:
        super().__init__(app)
        self._general = _FixedWindowLimiter(general_limit, general_window_seconds)
        self._auth_failures = _FixedWindowLimiter(auth_failure_limit, auth_failure_window_seconds)

    async def dispatch(self, request: Request, call_next) -> Response:
        key = _client_ip(request)

        blocked, retry_after = self._auth_failures.is_blocked(key)
        if blocked:
            return JSONResponse(
                {"detail": "too many failed auth attempts from this address — try again later"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        allowed, retry_after = self._general.hit(key)
        if not allowed:
            return JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        if response.status_code == 401:
            self._auth_failures.hit(key)
        return response


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
