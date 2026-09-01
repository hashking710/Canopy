import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from canopy_agent.notifications.email import _build_subject
from canopy_agent.services.error_reporting import report_system_error


class _EchoHandler(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        self.received.append(json.loads(self.rfile.read(length)))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture()
def echo_server():
    _EchoHandler.received = []
    server = HTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join()


# ---- real end-to-end: report_system_error -> notifications registry -> webhook ----


async def test_report_system_error_reaches_the_webhook_channel(echo_server, monkeypatch):
    port = echo_server.server_port
    monkeypatch.setenv("CANOPY_ALERT_WEBHOOK_URL", f"http://127.0.0.1:{port}/hook")

    await report_system_error("backup", "scheduled backup failed", ValueError("disk full"))

    assert len(_EchoHandler.received) == 1
    payload = _EchoHandler.received[0]
    assert payload["type"] == "system_error"
    assert payload["source"] == "backup"
    assert payload["message"] == "scheduled backup failed"
    assert "ValueError: disk full" in payload["exception"]
    assert "occurred_at" in payload


async def test_report_system_error_without_an_exception_object(echo_server, monkeypatch):
    port = echo_server.server_port
    monkeypatch.setenv("CANOPY_ALERT_WEBHOOK_URL", f"http://127.0.0.1:{port}/hook")

    await report_system_error("retention", "retention cycle failed")

    assert _EchoHandler.received[0]["exception"] is None


async def test_report_system_error_never_raises_when_nothing_is_configured(monkeypatch):
    monkeypatch.delenv("CANOPY_ALERT_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("CANOPY_ALERT_SMTP_HOST", raising=False)
    monkeypatch.delenv("CANOPY_ALERT_DISCORD_WEBHOOK_URL", raising=False)
    await report_system_error("poller", "poll cycle failed", RuntimeError("boom"))  # must not raise


async def test_report_system_error_survives_one_channel_failing(monkeypatch):
    """A broken/unreachable channel must not stop the others from being tried, or
    stop the caller (a background task's own except block) from continuing on."""
    from canopy_agent.notifications.base import NotificationChannel

    delivered = []

    class _Broken(NotificationChannel):
        plugin_name = "broken"

        async def send(self, alert: dict) -> None:
            raise RuntimeError("channel is down")

    class _Working(NotificationChannel):
        plugin_name = "working"

        async def send(self, alert: dict) -> None:
            delivered.append(alert)

    monkeypatch.setattr(
        "canopy_agent.services.error_reporting.get_active_channels",
        lambda: [_Broken(), _Working()],
    )

    await report_system_error("poller", "poll cycle failed")  # must not raise
    assert len(delivered) == 1
    assert delivered[0]["source"] == "poller"


async def test_report_system_error_survives_personal_notify_failing(monkeypatch):
    """Regression test: report_system_error is called from every background task's
    own except block (poller.py, retention.py, backup.py) — an uncaught exception
    here would propagate out of that except block and kill the calling task's
    entire while-True loop permanently (task.done() becomes True with no retry).
    A transient failure in the personal-notification path (e.g. the DB being
    momentarily locked by another concurrent background task at startup) must
    never be able to do that."""

    async def _boom(payload):
        raise RuntimeError("simulated transient DB failure")

    monkeypatch.setattr("canopy_agent.services.error_reporting.notify_operators_of_system_error", _boom)
    await report_system_error("poller", "poll cycle failed")  # must not raise


# ---- email subject line — type-aware, plant alert vs. system error ------------------


def test_build_subject_for_a_plant_alert():
    subject = _build_subject(
        {"room_id": "greenhouse-a", "metric": "temp_f", "condition": "gt", "threshold": 90.0, "value": 95.0}
    )
    assert subject == "Canopy alert: greenhouse-a temp_f gt 90.0 (now 95.0)"


def test_build_subject_for_a_system_error():
    subject = _build_subject({"type": "system_error", "source": "backup", "message": "scheduled backup failed"})
    assert subject == "Canopy system error: backup — scheduled backup failed"
