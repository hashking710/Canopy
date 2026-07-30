import asyncio
import json
import os
import urllib.request

from canopy_agent.notifications.base import NotificationChannel


class WebhookNotificationChannel(NotificationChannel):
    """POSTs the alert as JSON to a configured URL. Uses only the stdlib (urllib, off
    the event loop via asyncio.to_thread) rather than pulling in an HTTP client
    dependency for something this simple."""

    plugin_name = "Webhook"
    plugin_description = "POSTs a JSON payload to a configured URL (Slack incoming webhooks, a custom endpoint, etc.)."
    config_schema = {"CANOPY_ALERT_WEBHOOK_URL": "The URL to POST alert JSON to"}

    def __init__(self) -> None:
        self._url = os.environ.get("CANOPY_ALERT_WEBHOOK_URL")

    async def send(self, alert: dict) -> None:
        if not self._url:
            return
        await asyncio.to_thread(self._post, alert)

    def _post(self, alert: dict) -> None:
        request = urllib.request.Request(
            self._url,
            data=json.dumps(alert).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 300:
                raise RuntimeError(f"webhook returned HTTP {response.status}")
