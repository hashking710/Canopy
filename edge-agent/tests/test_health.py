from canopy_agent.services.health import get_task_health, record_failure, record_success


class _FakeTask:
    """The health endpoint only ever calls task.done() — a real asyncio.Task would
    work too, but ties the test to loop/threading plumbing that has nothing to do
    with what's actually being tested here."""

    def __init__(self, done: bool) -> None:
        self._done = done

    def done(self) -> bool:
        return self._done


# ---- services/health.py — pure, no HTTP involved -------------------------------------


def test_record_success_sets_last_success_at():
    record_success("test-task-1")
    health = get_task_health()
    assert health["test-task-1"].last_success_at is not None
    assert health["test-task-1"].last_error_at is None


def test_record_failure_sets_last_error_at():
    record_failure("test-task-2")
    health = get_task_health()
    assert health["test-task-2"].last_error_at is not None
    assert health["test-task-2"].last_success_at is None


def test_unknown_task_absent_from_health():
    assert "never-recorded-task" not in get_task_health()


def test_success_then_failure_keeps_both_timestamps():
    record_success("test-task-3")
    record_failure("test-task-3")
    health = get_task_health()
    assert health["test-task-3"].last_success_at is not None
    assert health["test-task-3"].last_error_at is not None


# ---- GET /api/health — real HTTP layer -----------------------------------------------


def test_health_reports_ok_with_database_reachable(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"]["reachable"] is True


def test_health_has_no_tasks_when_app_state_is_unset(client):
    # The lightweight test app (see conftest.py) never runs main.py's real
    # lifespan, so there's no app.state.background_tasks to report on — this
    # should degrade gracefully to an empty dict, not 500.
    resp = client.get("/api/health")
    assert resp.json()["tasks"] == {}


def test_health_reports_a_running_task_with_its_last_success(client):
    record_success("poller")
    client.app.state.background_tasks = {"poller": _FakeTask(done=False)}

    resp = client.get("/api/health")
    body = resp.json()
    assert body["status"] == "ok"
    assert body["tasks"]["poller"]["running"] is True
    assert body["tasks"]["poller"]["last_success_at"] is not None


def test_health_is_degraded_when_a_background_task_has_died(client):
    client.app.state.background_tasks = {"poller": _FakeTask(done=True)}

    resp = client.get("/api/health")
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["tasks"]["poller"]["running"] is False


def test_health_reports_last_error_for_a_failed_task_that_is_still_running(client):
    # A task can be "running" (its outer while-True loop is alive) while its most
    # recent cycle still failed — see poller.py's own try/except shape, where a
    # cycle failing doesn't kill the task, just that iteration.
    record_failure("retention")
    client.app.state.background_tasks = {"retention": _FakeTask(done=False)}

    resp = client.get("/api/health")
    body = resp.json()
    assert body["tasks"]["retention"]["running"] is True
    assert body["tasks"]["retention"]["last_error_at"] is not None
