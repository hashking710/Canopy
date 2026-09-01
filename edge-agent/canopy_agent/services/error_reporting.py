import logging
import traceback
from datetime import datetime, timezone

from canopy_agent.notifications.registry import get_active_channels

logger = logging.getLogger("canopy_agent.error_reporting")


async def report_system_error(source: str, message: str, exc: BaseException | None = None) -> None:
    """Dispatches a real software failure — not a plant-condition alert — through
    the same notification channels AlertEvents already use (webhook/email, each a
    no-op until its own env vars are configured, see notifications/registry.py).
    Zero new configuration surface, zero new dependency: a deployment that's
    already set up CANOPY_ALERT_WEBHOOK_URL or the SMTP vars for plant alerts gets
    software-failure reports through the same channel for free.

    Deliberately not wired into every `except Exception` in the codebase — the
    poller's per-room failures already surface via Room.last_poll_error in the
    dashboard UI, and several background tasks (MQTT publish/relay) are *expected*
    to fail gracefully on a single-Pi deployment with no broker configured, per
    their own existing comments. This is for failures that would otherwise be
    genuinely invisible outside server logs: a whole poll cycle crashing, a
    retention cycle failing, or a scheduled backup silently not happening for
    weeks before anyone notices.
    """
    # get_active_channels() always returns every registered channel (webhook,
    # email, discord, plus any plugin) regardless of whether each is actually
    # configured — same as services/alerts.py's dispatch_alert_notifications.
    # Each channel's own send() is the one that no-ops when its own env vars
    # aren't set, so there's no "nothing configured" short-circuit to make here.
    channels = get_active_channels()
    payload = {
        "type": "system_error",
        "source": source,
        "message": message,
        "exception": "".join(traceback.format_exception(exc)) if exc else None,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    for channel in channels:
        try:
            await channel.send(payload)
        except Exception:
            logger.exception(
                "notification channel '%s' failed to deliver a system-error report", channel.plugin_name
            )
