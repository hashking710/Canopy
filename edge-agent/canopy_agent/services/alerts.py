import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.models import AlertEvent, AlertRule
from canopy_agent.notifications.registry import get_active_channels
from canopy_agent.services.personal_notify import notify_operators_of_alert

logger = logging.getLogger("canopy_agent.alerts")


def _condition_breached(condition: str, value: float, threshold: float) -> bool:
    if condition == "gt":
        return value > threshold
    if condition == "lt":
        return value < threshold
    raise ValueError(f"unknown alert condition '{condition}'")


def evaluate_alerts_for_room(db: Session, room_id: str, values: dict[str, float]) -> list[AlertEvent]:
    """
    Called by the poller right after persisting a room's readings. Opens a new
    AlertEvent the moment a rule's condition is first breached, and resolves it the
    moment a later reading is back in range — so `resolved_at IS NULL` rows are always
    exactly "what's wrong right now", not a log that grows every poll cycle a
    condition stays breached. Returns newly-opened events, for notification dispatch.
    """
    rules = db.execute(
        select(AlertRule).where(AlertRule.room_id == room_id, AlertRule.enabled == True)  # noqa: E712
    ).scalars().all()

    newly_opened: list[AlertEvent] = []
    for rule in rules:
        if rule.metric not in values:
            continue
        value = values[rule.metric]
        breached = _condition_breached(rule.condition, value, rule.threshold)

        open_event = db.execute(
            select(AlertEvent).where(AlertEvent.rule_id == rule.id, AlertEvent.resolved_at.is_(None))
        ).scalar_one_or_none()

        if breached and open_event is None:
            event = AlertEvent(
                rule_id=rule.id,
                room_id=room_id,
                metric=rule.metric,
                value=value,
                threshold=rule.threshold,
                condition=rule.condition,
                severity=rule.severity,
            )
            db.add(event)
            db.flush()  # assign event.id so it's usable immediately by the caller
            newly_opened.append(event)
        elif not breached and open_event is not None:
            open_event.resolved_at = datetime.now(timezone.utc)

    return newly_opened


async def dispatch_alert_notifications(events: list[AlertEvent], room_id: str) -> None:
    if not events:
        return
    channels = get_active_channels()
    for event in events:
        payload = {
            "room_id": room_id,
            "metric": event.metric,
            "value": event.value,
            "threshold": event.threshold,
            "condition": event.condition,
            "severity": event.severity,
            "triggered_at": event.triggered_at.isoformat(),
        }
        for channel in channels:
            try:
                await channel.send(payload)
            except Exception:
                logger.exception("notification channel '%s' failed to deliver an alert", channel.plugin_name)
        # Facility-wide channels above are unconditional/shared; this additionally
        # emails any operator who's personally subscribed (see
        # services/personal_notify.py) — a distinct, opt-in delivery path, not a
        # duplicate of the above. Guarded the same way the channel loop above is:
        # a personal-notification failure must never propagate out of here and
        # take down the poller task that called this.
        try:
            await notify_operators_of_alert(payload)
        except Exception:
            logger.exception("failed to notify operators personally of an alert")
