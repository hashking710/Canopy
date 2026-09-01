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

    async def send(self, alert: dict) -> None:
        # Read fresh on every send, not cached at __init__ — notifications/registry.py
        # constructs one instance per channel for the whole process lifetime (same as
        # adapters/registry.py), so a URL set/changed after startup would otherwise
        # never take effect without a restart. Same hot-reload reasoning as the cloud
        # sensor adapters (see e.g. canopy-adapter-govee's read()).
        url = os.environ.get("CANOPY_ALERT_WEBHOOK_URL")
        if not url:
            return
        await asyncio.to_thread(self._post, url, alert)

    def _post(self, url: str, alert: dict) -> None:
        request = urllib.request.Request(
            url,
            data=json.dumps(alert).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 300:
                raise RuntimeError(f"webhook returned HTTP {response.status}")
