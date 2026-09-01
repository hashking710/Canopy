import asyncio
import json
import os
import smtplib
from dataclasses import dataclass
from email.mime.text import MIMEText

from canopy_agent.notifications.base import NotificationChannel


@dataclass
class _SmtpConfig:
    host: str
    port: int
    username: str | None
    password: str | None
    starttls: bool
    from_addr: str
    to_addr: str


def _load_smtp_config() -> _SmtpConfig | None:
    host = os.environ.get("CANOPY_ALERT_SMTP_HOST")
    from_addr = os.environ.get("CANOPY_ALERT_EMAIL_FROM")
    to_addr = os.environ.get("CANOPY_ALERT_EMAIL_TO")
    if not (host and from_addr and to_addr):
        return None
    return _SmtpConfig(
        host=host,
        port=int(os.environ.get("CANOPY_ALERT_SMTP_PORT", "587")),
        username=os.environ.get("CANOPY_ALERT_SMTP_USERNAME"),
        password=os.environ.get("CANOPY_ALERT_SMTP_PASSWORD"),
        starttls=os.environ.get("CANOPY_ALERT_SMTP_STARTTLS", "true").lower() != "false",
        from_addr=from_addr,
        to_addr=to_addr,
    )


class EmailNotificationChannel(NotificationChannel):
    """Sends alert notifications via SMTP (stdlib smtplib — standard protocol, no
    reverse-engineering involved, unlike some of this project's other integrations).
    Configured entirely via env vars; inactive (send() is a no-op) until both a host
    and a recipient are set."""

    plugin_name = "Email"
    plugin_description = "Sends alert notifications over SMTP."
    config_schema = {
        "CANOPY_ALERT_SMTP_HOST": "SMTP server hostname",
        "CANOPY_ALERT_SMTP_PORT": "SMTP port (default 587)",
        "CANOPY_ALERT_SMTP_USERNAME": "optional SMTP auth username",
        "CANOPY_ALERT_SMTP_PASSWORD": "optional SMTP auth password",
        "CANOPY_ALERT_SMTP_STARTTLS": "'false' to disable STARTTLS (default enabled)",
        "CANOPY_ALERT_EMAIL_FROM": "From address",
        "CANOPY_ALERT_EMAIL_TO": "To address",
    }

    async def send(self, alert: dict) -> None:
        # Read fresh on every send, not cached at __init__ — see webhook.py's
        # send() for why (one instance per channel is shared across the process
        # lifetime, so config set/changed after startup must still take effect).
        config = _load_smtp_config()
        if config is None:
            return
        await asyncio.to_thread(self._send_sync, config, alert)

    def _send_sync(self, config: _SmtpConfig, alert: dict) -> None:
        message = MIMEText(json.dumps(alert, indent=2))
        message["Subject"] = _build_subject(alert)
        message["From"] = config.from_addr
        message["To"] = config.to_addr

        with smtplib.SMTP(config.host, config.port, timeout=10) as server:
            if config.starttls:
                server.starttls()
            if config.username and config.password:
                server.login(config.username, config.password)
            server.send_message(message)


def _build_subject(alert: dict) -> str:
    # Two distinct shapes flow through the same channel: plant-condition alerts
    # (services/alerts.py) and software-failure reports (services/error_reporting.py)
    # — same "reuse the delivery mechanism, not the payload shape" reasoning as
    # webhook.py just JSON-POSTing whatever dict it's given either way.
    if alert.get("type") == "system_error":
        return f"Canopy system error: {alert.get('source')} — {alert.get('message')}"
    return (
        f"Canopy alert: {alert.get('room_id')} {alert.get('metric')} "
        f"{alert.get('condition')} {alert.get('threshold')} (now {alert.get('value')})"
    )
