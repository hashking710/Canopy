from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.deps import get_db
from canopy_agent.services.health import get_task_health

router = APIRouter(prefix="/api/health", tags=["health"])


def _iso(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


@router.get("")
def health(request: Request, db: Session = Depends(get_db)) -> dict:
    """Used to just return a bare {"status": "ok"} regardless of what was actually
    happening — nothing would notice if the poller silently stopped looping, or if
    retention/backup had been failing for days. Deliberately not behind
    require_token (see main.py's router registration): health checks (Docker
    healthcheck, an external monitor) need to be reachable without a credential,
    same reasoning as every health-check endpoint anywhere — and nothing returned
    here is sensitive (no secrets, no stack traces, just booleans/timestamps)."""
    db_reachable = True
    try:
        db.execute(select(1))
    except Exception:
        db_reachable = False

    task_health = get_task_health()
    tasks = {}
    all_tasks_running = True
    # app.state.background_tasks is set in main.py's lifespan — absent in a
    # lightweight test app that doesn't run the real lifespan (see conftest.py),
    # hence the getattr default rather than assuming it's always there.
    for name, task in getattr(request.app.state, "background_tasks", {}).items():
        running = not task.done()
        all_tasks_running = all_tasks_running and running
        health_entry = task_health.get(name)
        tasks[name] = {
            "running": running,
            "last_success_at": _iso(health_entry.last_success_at) if health_entry else None,
            "last_error_at": _iso(health_entry.last_error_at) if health_entry else None,
        }

    status = "ok" if db_reachable and all_tasks_running else "degraded"
    return {"status": status, "database": {"reachable": db_reachable}, "tasks": tasks}
