import asyncio
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

if sys.platform == "win32":
    # paho-mqtt (via aiomqtt) needs loop.add_reader/add_writer, which Windows' default
    # ProactorEventLoop doesn't implement. Linux (the real deployment target for master,
    # same as the edge agent) doesn't hit this.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from canopy_master.auth import require_token
from canopy_master.db import Base, engine
from canopy_master.mqtt_subscriber import subscribe_forever
from canopy_master.routers import audit, sites, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    # No Alembic here (unlike edge-agent) — this is a brand-new, small schema with no
    # prior deployments to migrate from yet. create_all is a deliberate, documented
    # choice for a v1, not an oversight; see canopy_master/models.py.
    Base.metadata.create_all(engine)
    subscriber_task = asyncio.create_task(subscribe_forever())
    try:
        yield
    finally:
        subscriber_task.cancel()


app = FastAPI(title="Canopy Master", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sites.router, dependencies=[Depends(require_token)])
app.include_router(audit.router, dependencies=[Depends(require_token)])
app.include_router(ws.router)  # WS auth is checked inside the handler (query param, not a header)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
