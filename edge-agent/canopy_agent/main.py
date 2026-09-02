import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Before any other canopy_agent module is imported — several of them log at import
# or first-call time (adapter registry load failures, etc.), and those should go
# through the real configured handler/format too, not whatever bare logging.warning
# would do with zero handlers attached.
from canopy_agent.logging_config import configure_logging

configure_logging("edge-agent")

if sys.platform == "win32":
    # paho-mqtt (via aiomqtt, used for the optional MQTT publisher) needs
    # loop.add_reader/add_writer, which Windows' default ProactorEventLoop doesn't
    # implement. Linux (the real deployment target, Raspberry Pi) doesn't hit this.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from canopy_agent.auth import require_token
from canopy_agent.db import SessionLocal
from canopy_agent.migrate import upgrade_to_head
from canopy_agent.routers import alerts, backup as backup_router, compliance, facility, health as health_router, license as license_router, menu_sync as menu_sync_router, operators, rooms, secrets as secrets_router, strains as strains_router, version as version_router, ws
from canopy_agent.seed import seed
from canopy_agent.seed_compliance import seed_compliance
from canopy_agent.services.audit_relay import subscribe_relay_forever
from canopy_agent.services.backup import backup_forever
from canopy_agent.services.demo_reset import demo_reset_forever, reset_demo_data
from canopy_agent.services.error_reporting import report_system_error
from canopy_agent.services.menu_sync_task import menu_sync_forever
from canopy_agent.services.poller import poll_forever
from canopy_agent.services.rate_limit import RateLimitMiddleware
from canopy_agent.services.retention import retention_forever
from canopy_agent.services.secrets_bootstrap import load_secrets_into_environ


SEED_DEMO_DATA = os.environ.get("CANOPY_SEED_DEMO_DATA", "false").lower() in ("1", "true", "yes")
# A public, interactive demo instance — not the same as SEED_DEMO_DATA (which just
# pre-populates a normal, single-tenant deployment once). Demo mode additionally
# resets on a fixed interval (so visitor tampering can't accumulate) and rate-limits
# requests. See docs/ once deployed at demo.canopy.hkdev.run.
DEMO_MODE = os.environ.get("CANOPY_DEMO_MODE", "false").lower() in ("1", "true", "yes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    upgrade_to_head()

    # Before anything else touches os.environ (the poller, adapter construction) —
    # a credential set via the dashboard (routers/secrets.py) needs to survive a
    # restart, and this is what replays it back into the process environment every
    # adapter still reads from. DB wins over whatever docker-compose.yml/.env
    # already set, since that's the "someone explicitly configured this via the
    # UI" path.
    db = SessionLocal()
    try:
        load_secrets_into_environ(db)
    finally:
        db.close()

    if DEMO_MODE:
        # Always start from a known-good demo dataset, whether this is a fresh
        # volume or a restart of a long-running demo container.
        db = SessionLocal()
        try:
            reset_demo_data(db)
        finally:
            db.close()
    elif SEED_DEMO_DATA:
        # Off by default — a real deployment (what actually ships) starts on a truly
        # empty facility, not the GMO/Jelly Breath demo greenhouse. Opt in only for
        # trying the dashboard out before any real rooms exist; see README.md.
        db = SessionLocal()
        try:
            seed(db)
            seed_compliance(db)
        finally:
            db.close()

    # Named (not just a plain list) so /api/health can report per-task liveness —
    # task.done() means it crashed out of its own infinite loop entirely (a bug in
    # the loop itself, not a single cycle's exception, which each loop already
    # catches internally — see poller.py/retention.py/backup.py's own try/except).
    named_tasks = {
        "poller": asyncio.create_task(poll_forever()),
        "retention": asyncio.create_task(retention_forever()),
        "audit_relay": asyncio.create_task(subscribe_relay_forever()),
        "menu_sync": asyncio.create_task(menu_sync_forever()),
    }
    if DEMO_MODE:
        named_tasks["demo_reset"] = asyncio.create_task(demo_reset_forever())
    else:
        # Not in demo mode: real data worth protecting. A public demo resets hourly
        # by design, so backing up an intentionally throwaway/tamperable dataset would
        # just fill disk with useless snapshots.
        named_tasks["backup"] = asyncio.create_task(backup_forever())
    app.state.background_tasks = named_tasks
    try:
        yield
    finally:
        for task in named_tasks.values():
            task.cancel()


logger = logging.getLogger("canopy_agent.main")

app = FastAPI(title="Canopy Edge Agent", lifespan=lifespan)


@app.exception_handler(Exception)
async def _report_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI's own default 500 handling already returns a generic error response
    — this only adds the report_system_error dispatch on top, so a genuinely
    unexpected route-handler crash (not a normal HTTPException — those never reach
    here) reaches the same webhook/email channels as a background-task failure,
    instead of only ever showing up in server logs."""
    logger.exception("unhandled exception in %s %s", request.method, request.url.path)
    await report_system_error("http", f"unhandled exception in {request.method} {request.url.path}", exc)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


app.add_middleware(
    CORSMiddleware,
    # A public demo's frontend/API pair are served from a different port locally
    # (and, once deployed, ideally the same origin behind a reverse proxy — see
    # deploy/docker-compose.demo.yml) — no cookies/credentials flow through this API,
    # so allowing any origin here is no more exposed than the API already is by
    # design in demo mode (publicly interactive, rate-limited, reset hourly).
    allow_origins=["*"] if DEMO_MODE else ["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Always mounted, not just in demo mode — the general limit is generous enough
# (120/min per IP by default, see services/rate_limit.py) to never brush against
# real dashboard usage, but a real deployment reachable beyond a pure LAN (see
# docs/deployment-tls.md) had no rate limiting at all before this. Demo mode gets a
# tighter general cap, since it's deliberately publicly writable, on top of the
# same auth-failure throttle every deployment gets.
_rate_limit_kwargs = {"general_limit": 60} if DEMO_MODE else {}
app.add_middleware(RateLimitMiddleware, **_rate_limit_kwargs)

app.include_router(facility.router, dependencies=[Depends(require_token)])
app.include_router(rooms.router, dependencies=[Depends(require_token)])
app.include_router(ws.router)  # WS auth is checked inside the handler (query param, not a header)
app.include_router(compliance.router, dependencies=[Depends(require_token)])
app.include_router(operators.router, dependencies=[Depends(require_token)])
app.include_router(alerts.router, dependencies=[Depends(require_token)])
app.include_router(license_router.router, dependencies=[Depends(require_token)])
app.include_router(backup_router.router, dependencies=[Depends(require_token)])
app.include_router(secrets_router.router, dependencies=[Depends(require_token)])
app.include_router(strains_router.router, dependencies=[Depends(require_token)])
app.include_router(menu_sync_router.router, dependencies=[Depends(require_token)])
app.include_router(version_router.router, dependencies=[Depends(require_token)])
app.include_router(health_router.router)  # no require_token — see health.py's own docstring
