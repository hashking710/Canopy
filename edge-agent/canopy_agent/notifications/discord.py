import asyncio
import json
import os
import urllib.request

from canopy_agent.notifications.base import NotificationChannel

# Discord embed side-bar colors (decimal, not hex) by severity — matches the
# same warn/danger split used for badges elsewhere in this project.
_SEVERITY_COLOR = {
    "critical": 0xE05555,  # danger
    "warning": 0xD9A63C,  # warn
}
_DEFAULT_COLOR = 0x5B8DEF  # default/info


class DiscordNotificationChannel(NotificationChannel):
    """POSTs alerts to a Discord incoming webhook. A separate channel from the generic
    WebhookNotificationChannel because Discord's webhook API rejects arbitrary JSON —
    it only accepts a payload shaped like {"embeds": [...]}, not a raw alert dict."""

    plugin_name = "Discord"
    plugin_description = "Posts alert notifications to a Discord channel via an incoming webhook."
    config_schema = {"CANOPY_ALERT_DISCORD_WEBHOOK_URL": "A Discord incoming webhook URL"}

    def __init__(self) -> None:
        self._url = os.environ.get("CANOPY_ALERT_DISCORD_WEBHOOK_URL")

    async def send(self, alert: dict) -> None:
        if not self._url:
            return
        await asyncio.to_thread(self._post, alert)

    def _post(self, alert: dict) -> None:
        request = urllib.request.Request(
            self._url,
            data=json.dumps({"embeds": [_build_embed(alert)]}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 300:
                raise RuntimeError(f"discord webhook returned HTTP {response.status}")


def _build_embed(alert: dict) -> dict:
    room_id = alert.get("room_id", "unknown room")
    metric = alert.get("metric")
    condition = alert.get("condition")
    threshold = alert.get("threshold")
    value = alert.get("value")
    severity = alert.get("severity")

    embed: dict = {
        "title": f"Canopy alert: {room_id}",
        "description": f"**{metric}** {condition} {threshold} — currently **{value}**",
        "color": _SEVERITY_COLOR.get(severity, _DEFAULT_COLOR),
        "fields": [{"name": "Severity", "value": str(severity or "unknown"), "inline": True}],
    }
    triggered_at = alert.get("triggered_at")
    if triggered_at:
        embed["timestamp"] = triggered_at
    return embed
