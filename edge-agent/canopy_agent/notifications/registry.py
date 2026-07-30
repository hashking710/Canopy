import logging
from importlib.metadata import EntryPoint, entry_points

from canopy_agent.notifications.base import NotificationChannel
from canopy_agent.notifications.discord import DiscordNotificationChannel
from canopy_agent.notifications.email import EmailNotificationChannel
from canopy_agent.notifications.webhook import WebhookNotificationChannel

logger = logging.getLogger("canopy_agent.notifications.registry")

# Same discovery shape as adapters/registry.py and compliance_sync/registry.py: entries
# in this group are separately installed plugin packages (e.g. SMS, Slack, PagerDuty),
# merged with "webhook" and "email" which this package provides itself.
PLUGIN_GROUP = "canopy.notification_channels"

_instances: dict[str, NotificationChannel] | None = None


def _load_channels() -> dict[str, NotificationChannel]:
    global _instances
    if _instances is not None:
        return _instances

    factories: dict[str, type[NotificationChannel]] = {
        "webhook": WebhookNotificationChannel,
        "email": EmailNotificationChannel,
        "discord": DiscordNotificationChannel,
    }
    for ep in entry_points(group=PLUGIN_GROUP):
        _register_plugin(factories, ep)

    _instances = {name: cls() for name, cls in factories.items()}
    return _instances


def _register_plugin(factories: dict[str, type[NotificationChannel]], ep: EntryPoint) -> None:
    try:
        channel_cls = ep.load()
    except Exception:
        logger.exception("failed to load notification channel plugin '%s' — skipping it", ep.name)
        return
    if not (isinstance(channel_cls, type) and issubclass(channel_cls, NotificationChannel)):
        logger.error("notification channel plugin '%s' does not point at a NotificationChannel subclass", ep.name)
        return
    if ep.name in factories:
        logger.warning("notification channel plugin '%s' conflicts with an existing channel — skipping it", ep.name)
        return
    factories[ep.name] = channel_cls


def get_active_channels() -> list[NotificationChannel]:
    return list(_load_channels().values())
