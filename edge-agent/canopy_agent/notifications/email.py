import asyncio
import json
import os
import smtplib
from email.mime.text import MIMEText

from canopy_agent.notifications.base import NotificationChannel


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

    def __init__(self) -> None:
        self._host = os.environ.get("CANOPY_ALERT_SMTP_HOST")
        self._port = int(os.environ.get("CANOPY_ALERT_SMTP_PORT", "587"))
        self._username = os.environ.get("CANOPY_ALERT_SMTP_USERNAME")
        self._password = os.environ.get("CANOPY_ALERT_SMTP_PASSWORD")
        self._starttls = os.environ.get("CANOPY_ALERT_SMTP_STARTTLS", "true").lower() != "false"
        self._from_addr = os.environ.get("CANOPY_ALERT_EMAIL_FROM")
        self._to_addr = os.environ.get("CANOPY_ALERT_EMAIL_TO")

    async def send(self, alert: dict) -> None:
        if not (self._host and self._from_addr and self._to_addr):
            return
        await asyncio.to_thread(self._send_sync, alert)

    def _send_sync(self, alert: dict) -> None:
        message = MIMEText(json.dumps(alert, indent=2))
        message["Subject"] = (
            f"Canopy alert: {alert.get('room_id')} {alert.get('metric')} "
            f"{alert.get('condition')} {alert.get('threshold')} (now {alert.get('value')})"
        )
        message["From"] = self._from_addr
        message["To"] = self._to_addr

        with smtplib.SMTP(self._host, self._port, timeout=10) as server:
            if self._starttls:
                server.starttls()
            if self._username and self._password:
                server.login(self._username, self._password)
            server.send_message(message)
