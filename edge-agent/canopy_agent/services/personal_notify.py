import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.compliance_models import Operator
from canopy_agent.db import SessionLocal
from canopy_agent.notifications.email import send_personal_email

logger = logging.getLogger("canopy_agent.personal_notify")

# Same rank idea as services/operators.py's ROLE_RANK, for a completely different
# axis (event urgency, not permission) — "warning" is the more permissive minimum,
# "critical" is stricter (only critical events reach an operator subscribed at that
# level).
_SEVERITY_RANK = {"warning": 0, "critical": 1}


async def _notify_qualifying_operators(db: Session, payload: dict, flag_column, event_severity: str | None) -> None:
    """Finds active operators who've opted into this category and supplied an
    email, filters by their own minimum-severity preference, and emails each one
    individually."""
    operators = db.execute(
        select(Operator).where(
            Operator.active == True,  # noqa: E712
            flag_column == True,  # noqa: E712
            Operator.notify_email.isnot(None),
        )
    ).scalars().all()

    event_rank = _SEVERITY_RANK.get(event_severity, _SEVERITY_RANK["critical"])
    for operator in operators:
        if _SEVERITY_RANK.get(operator.notify_min_severity, _SEVERITY_RANK["critical"]) > event_rank:
            continue
        try:
            await send_personal_email(operator.notify_email, payload)
        except Exception:
            logger.exception("failed to send a personal notification email to operator '%s'", operator.name)


async def notify_operators_of_alert(payload: dict, db: Session | None = None) -> None:
    """payload is the same room-alert dict services/alerts.py's
    dispatch_alert_notifications already builds for the facility-wide channels —
    reused as-is, not reshaped, same "one payload shape, multiple delivery targets"
    approach that module already takes.

    Opens its own short-lived session by default (production callers — a background
    task's except block, a global exception handler — don't reliably have one in
    scope, same reasoning as poller.py/retention.py's own `_forever()` wrappers);
    pass `db` explicitly to reuse an existing session (mainly for tests, same
    "the _forever() wrapper opens a session, the real logic takes one as a
    parameter" split retention.py already uses)."""
    owns_session = db is None
    db = db or SessionLocal()
    try:
        await _notify_qualifying_operators(db, payload, Operator.notify_on_alerts, payload.get("severity"))
    finally:
        if owns_session:
            db.close()


async def notify_operators_of_system_error(payload: dict, db: Session | None = None) -> None:
    """System errors have no severity field of their own (see
    services/error_reporting.py) — always treated as the stricter "critical" so the
    severity filter still applies consistently; in practice this just means
    "opted in via notify_on_system_errors or not". See notify_operators_of_alert's
    docstring for the `db` parameter's purpose."""
    owns_session = db is None
    db = db or SessionLocal()
    try:
        await _notify_qualifying_operators(db, payload, Operator.notify_on_system_errors, "critical")
    finally:
        if owns_session:
            db.close()
