import time
from dataclasses import dataclass

# Before this existed, /api/health returned a bare {"status": "ok"} no matter what
# was actually happening — nothing would notice if the poller silently stopped
# looping, or if retention/backup had been failing for days. Background tasks
# report into this shared, in-process tracker; the health endpoint reads it back.
# Same "single-process, in-memory" scope as services/rate_limit.py — this is a
# liveness signal for the one process it's running in, not a distributed system.


@dataclass
class TaskHealth:
    last_success_at: float | None = None
    last_error_at: float | None = None


_task_health: dict[str, TaskHealth] = {}


def record_success(task_name: str) -> None:
    _task_health.setdefault(task_name, TaskHealth()).last_success_at = time.time()


def record_failure(task_name: str) -> None:
    _task_health.setdefault(task_name, TaskHealth()).last_error_at = time.time()


def get_task_health() -> dict[str, TaskHealth]:
    return dict(_task_health)
