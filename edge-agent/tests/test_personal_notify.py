import asyncio
import socket

import pytest
from aiosmtpd.controller import Controller

from canopy_agent.compliance_models import Operator
from canopy_agent.services.personal_notify import notify_operators_of_alert, notify_operators_of_system_error


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _CapturingHandler:
    def __init__(self):
        self.messages: list = []

    async def handle_DATA(self, server, session, envelope):
        self.messages.append(envelope)
        return "250 OK"


@pytest.fixture()
def smtp_server(monkeypatch):
    handler = _CapturingHandler()
    controller = Controller(handler, hostname="127.0.0.1", port=_free_port())
    controller.start()
    monkeypatch.setenv("CANOPY_ALERT_SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("CANOPY_ALERT_SMTP_PORT", str(controller.port))
    monkeypatch.setenv("CANOPY_ALERT_SMTP_STARTTLS", "false")
    monkeypatch.setenv("CANOPY_ALERT_EMAIL_FROM", "canopy@example.com")
    monkeypatch.delenv("CANOPY_ALERT_EMAIL_TO", raising=False)  # personal send doesn't need this
    monkeypatch.delenv("CANOPY_ALERT_SMTP_USERNAME", raising=False)
    try:
        yield handler
    finally:
        controller.stop()


def make_operator(db_session, **overrides):
    defaults = dict(
        id="op-1", name="Grower Greg", role="operator", active=True,
        notify_email="greg@example.com", notify_on_alerts=True, notify_on_system_errors=True,
        notify_min_severity="critical",
    )
    defaults.update(overrides)
    operator = Operator(**defaults)
    db_session.add(operator)
    db_session.commit()
    return operator


async def test_notify_operators_of_alert_emails_a_subscribed_operator(db_session, smtp_server):
    make_operator(db_session)
    await notify_operators_of_alert({"room_id": "greenhouse-a", "metric": "temp_f", "severity": "critical"}, db_session)

    await asyncio.sleep(0.1)
    assert len(smtp_server.messages) == 1
    assert smtp_server.messages[0].rcpt_tos == ["greg@example.com"]


async def test_does_not_email_an_operator_who_has_not_opted_in(db_session, smtp_server):
    make_operator(db_session, notify_on_alerts=False)
    await notify_operators_of_alert({"room_id": "greenhouse-a", "severity": "critical"}, db_session)

    await asyncio.sleep(0.1)
    assert smtp_server.messages == []


async def test_does_not_email_an_operator_with_no_email_set(db_session, smtp_server):
    make_operator(db_session, notify_email=None)
    await notify_operators_of_alert({"room_id": "greenhouse-a", "severity": "critical"}, db_session)

    await asyncio.sleep(0.1)
    assert smtp_server.messages == []


async def test_does_not_email_an_inactive_operator(db_session, smtp_server):
    make_operator(db_session, active=False)
    await notify_operators_of_alert({"room_id": "greenhouse-a", "severity": "critical"}, db_session)

    await asyncio.sleep(0.1)
    assert smtp_server.messages == []


async def test_filters_out_events_below_the_operators_minimum_severity(db_session, smtp_server):
    make_operator(db_session, notify_min_severity="critical")
    await notify_operators_of_alert({"room_id": "greenhouse-a", "severity": "warning"}, db_session)

    await asyncio.sleep(0.1)
    assert smtp_server.messages == []


async def test_a_warning_subscriber_gets_both_warning_and_critical_events(db_session, smtp_server):
    make_operator(db_session, notify_min_severity="warning")
    await notify_operators_of_alert({"room_id": "greenhouse-a", "severity": "warning"}, db_session)
    await notify_operators_of_alert({"room_id": "greenhouse-a", "severity": "critical"}, db_session)

    await asyncio.sleep(0.1)
    assert len(smtp_server.messages) == 2


async def test_notify_operators_of_system_error_uses_its_own_flag(db_session, smtp_server):
    make_operator(db_session, notify_on_alerts=False, notify_on_system_errors=True)
    await notify_operators_of_system_error({"type": "system_error", "source": "poller"}, db_session)

    await asyncio.sleep(0.1)
    assert len(smtp_server.messages) == 1


async def test_no_smtp_configured_is_a_silent_noop(db_session, monkeypatch):
    monkeypatch.delenv("CANOPY_ALERT_SMTP_HOST", raising=False)
    make_operator(db_session)
    await notify_operators_of_alert({"room_id": "greenhouse-a", "severity": "critical"}, db_session)  # must not raise


async def test_multiple_subscribed_operators_are_each_notified_independently(db_session, smtp_server):
    make_operator(db_session, id="op-1", name="Greg", notify_email="greg@example.com")
    make_operator(db_session, id="op-2", name="Robin", notify_email="robin@example.com")
    await notify_operators_of_alert({"room_id": "greenhouse-a", "severity": "critical"}, db_session)

    await asyncio.sleep(0.1)
    recipients = {m.rcpt_tos[0] for m in smtp_server.messages}
    assert recipients == {"greg@example.com", "robin@example.com"}
