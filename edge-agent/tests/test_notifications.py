import asyncio
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from aiosmtpd.controller import Controller

from canopy_agent.notifications.discord import DiscordNotificationChannel
from canopy_agent.notifications.email import EmailNotificationChannel
from canopy_agent.notifications.webhook import WebhookNotificationChannel


class _EchoHandler(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        self.received.append(json.loads(self.rfile.read(length)))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass  # keep test output quiet


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


async def test_webhook_channel_delivers_real_http_post(echo_server, monkeypatch):
    port = echo_server.server_port
    monkeypatch.setenv("CANOPY_ALERT_WEBHOOK_URL", f"http://127.0.0.1:{port}/hook")

    channel = WebhookNotificationChannel()
    await channel.send({"room_id": "greenhouse-a", "metric": "temp_f", "value": 95.0, "threshold": 90.0, "condition": "gt"})

    assert _EchoHandler.received == [
        {"room_id": "greenhouse-a", "metric": "temp_f", "value": 95.0, "threshold": 90.0, "condition": "gt"}
    ]


async def test_webhook_channel_noop_when_unconfigured(monkeypatch):
    monkeypatch.delenv("CANOPY_ALERT_WEBHOOK_URL", raising=False)
    channel = WebhookNotificationChannel()
    await channel.send({"room_id": "x"})  # must not raise


class _CapturingHandler:
    messages: list = []

    async def handle_DATA(self, server, session, envelope):
        self.messages.append(envelope)
        return "250 OK"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def smtp_server():
    handler = _CapturingHandler()
    handler.messages = []
    controller = Controller(handler, hostname="127.0.0.1", port=_free_port())
    controller.start()
    try:
        yield controller, handler
    finally:
        controller.stop()


async def test_email_channel_delivers_real_smtp_message(smtp_server, monkeypatch):
    controller, handler = smtp_server
    monkeypatch.setenv("CANOPY_ALERT_SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("CANOPY_ALERT_SMTP_PORT", str(controller.port))
    monkeypatch.setenv("CANOPY_ALERT_SMTP_STARTTLS", "false")
    monkeypatch.setenv("CANOPY_ALERT_EMAIL_FROM", "canopy@example.com")
    monkeypatch.setenv("CANOPY_ALERT_EMAIL_TO", "grower@example.com")
    monkeypatch.delenv("CANOPY_ALERT_SMTP_USERNAME", raising=False)

    channel = EmailNotificationChannel()
    await channel.send({"room_id": "greenhouse-a", "metric": "temp_f", "value": 95.0, "threshold": 90.0, "condition": "gt"})

    await asyncio.sleep(0.1)  # aiosmtpd handles the message asynchronously in its own thread
    assert len(handler.messages) == 1
    assert handler.messages[0].mail_from == "canopy@example.com"
    assert handler.messages[0].rcpt_tos == ["grower@example.com"]
    assert b"greenhouse-a" in handler.messages[0].content


async def test_email_channel_noop_when_unconfigured(monkeypatch):
    monkeypatch.delenv("CANOPY_ALERT_SMTP_HOST", raising=False)
    channel = EmailNotificationChannel()
    await channel.send({"room_id": "x"})  # must not raise


class _FailingHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers["Content-Length"])
        self.rfile.read(length)
        self.send_response(500)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture()
def failing_server():
    server = HTTPServer(("127.0.0.1", 0), _FailingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join()


async def test_discord_channel_posts_a_real_embed(echo_server, monkeypatch):
    port = echo_server.server_port
    monkeypatch.setenv("CANOPY_ALERT_DISCORD_WEBHOOK_URL", f"http://127.0.0.1:{port}/hook")

    channel = DiscordNotificationChannel()
    await channel.send(
        {
            "room_id": "greenhouse-a",
            "metric": "temp_f",
            "value": 95.0,
            "threshold": 90.0,
            "condition": "gt",
            "severity": "critical",
            "triggered_at": "2026-03-15T18:30:00+00:00",
        }
    )

    assert len(_EchoHandler.received) == 1
    body = _EchoHandler.received[0]
    assert "embeds" in body and len(body["embeds"]) == 1
    embed = body["embeds"][0]
    assert "greenhouse-a" in embed["title"]
    assert "temp_f" in embed["description"]
    assert "95.0" in embed["description"]
    assert embed["color"] == 0xE05555  # critical severity color
    assert embed["timestamp"] == "2026-03-15T18:30:00+00:00"


async def test_discord_channel_noop_when_unconfigured(monkeypatch):
    monkeypatch.delenv("CANOPY_ALERT_DISCORD_WEBHOOK_URL", raising=False)
    channel = DiscordNotificationChannel()
    await channel.send({"room_id": "x"})  # must not raise


async def test_discord_channel_raises_on_non_2xx_response(failing_server, monkeypatch):
    port = failing_server.server_port
    monkeypatch.setenv("CANOPY_ALERT_DISCORD_WEBHOOK_URL", f"http://127.0.0.1:{port}/hook")

    channel = DiscordNotificationChannel()
    with pytest.raises(Exception):
        await channel.send({"room_id": "greenhouse-a"})
