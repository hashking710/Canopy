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
    to_addr: str | None  # None for _load_smtp_config_for_personal_send — see its own docstring


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


def _load_smtp_config_for_personal_send() -> _SmtpConfig | None:
    """Same SMTP server as the facility-wide email channel, but without requiring
    CANOPY_ALERT_EMAIL_TO — a personal notification (services/personal_notify.py)
    supplies its own per-operator recipient instead. Returns None if the facility
    hasn't configured SMTP at all: "set up SMTP once for the facility, then anyone
    can subscribe personally" — not a second, separate SMTP configuration surface."""
    host = os.environ.get("CANOPY_ALERT_SMTP_HOST")
    from_addr = os.environ.get("CANOPY_ALERT_EMAIL_FROM")
    if not (host and from_addr):
        return None
    return _SmtpConfig(
        host=host,
        port=int(os.environ.get("CANOPY_ALERT_SMTP_PORT", "587")),
        username=os.environ.get("CANOPY_ALERT_SMTP_USERNAME"),
        password=os.environ.get("CANOPY_ALERT_SMTP_PASSWORD"),
        starttls=os.environ.get("CANOPY_ALERT_SMTP_STARTTLS", "true").lower() != "false",
        from_addr=from_addr,
        to_addr=None,
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
        await asyncio.to_thread(_send_sync, config, alert, config.to_addr)


def _send_sync(config: _SmtpConfig, alert: dict, to_addr: str) -> None:
    message = MIMEText(json.dumps(alert, indent=2))
    message["Subject"] = _build_subject(alert)
    message["From"] = config.from_addr
    message["To"] = to_addr

    with smtplib.SMTP(config.host, config.port, timeout=10) as server:
        if config.starttls:
            server.starttls()
        if config.username and config.password:
            server.login(config.username, config.password)
        server.send_message(message)


async def send_personal_email(to_addr: str, alert: dict) -> None:
    """Delivers `alert` to one specific operator's own address, reusing the
    facility's shared SMTP config (see _load_smtp_config_for_personal_send) rather
    than the single facility-wide CANOPY_ALERT_EMAIL_TO recipient
    EmailNotificationChannel sends to. Silently no-ops if the facility hasn't
    configured SMTP at all — same "no-op until its own env vars are set" posture
    every notification channel already has."""
    config = _load_smtp_config_for_personal_send()
    if config is None:
        return
    await asyncio.to_thread(_send_sync, config, alert, to_addr)


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
