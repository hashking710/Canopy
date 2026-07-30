from sqlalchemy import select

from canopy_agent.compliance_models import AuditLogEntry
from canopy_agent.services.audit import record_audit, verify_audit_chain


def test_clean_chain_verifies_intact(db_session):
    record_audit(db_session, "plant", "p1", "created", "Alex", details={"x": 1})
    record_audit(db_session, "plant", "p1", "tagged", "Alex", details={"y": 2})
    record_audit(db_session, "harvest", "h1", "created", "Jordan")
    db_session.commit()

    assert verify_audit_chain(db_session) == []


def test_chain_survives_a_fresh_session_reload(db_session):
    # Guards against the SQLite naive/aware DateTime round-trip issue noted in
    # services/audit.py: hashing must produce the same result whether occurred_at is
    # the tz-aware value from write time or the naive value SQLite hands back later.
    record_audit(db_session, "plant", "p1", "created", "Alex")
    record_audit(db_session, "plant", "p1", "destroyed", "Alex")
    db_session.commit()
    db_session.expire_all()  # force every attribute to be reloaded from the DB on next access

    assert verify_audit_chain(db_session) == []


def test_tampering_with_a_historical_entry_is_detected(db_session):
    record_audit(db_session, "plant", "p1", "created", "Alex")
    record_audit(db_session, "plant", "p1", "tagged", "Alex")
    record_audit(db_session, "plant", "p1", "destroyed", "Alex")
    db_session.commit()

    first_entry = db_session.execute(select(AuditLogEntry).order_by(AuditLogEntry.id)).scalars().first()
    first_entry.action = "quietly_edited"  # simulated tampering
    db_session.commit()

    broken = verify_audit_chain(db_session)
    assert first_entry.id in broken


def test_chain_links_correctly_across_multiple_calls_in_one_transaction(db_session):
    # Endpoints like tag_plants call record_audit multiple times before a single
    # commit — each call must see the previous one's hash even before anything's
    # actually been committed to the database.
    first = record_audit(db_session, "plant_batch", "b1", "created", "Alex")
    second = record_audit(db_session, "plant", "p1", "tagged", "Alex")
    db_session.commit()

    assert second.prev_hash == first.entry_hash
    assert verify_audit_chain(db_session) == []


def test_verify_endpoint_reports_intact_for_real_compliance_actions(client, operator_id):
    client.post(
        "/api/compliance/plant-batches",
        json={
            "name": "AUDIT-TEST-001", "batch_type": "Clone", "strain": "Test Strain", "room_id": "test-room",
            "planted_date": "2026-07-01", "count": 3, "operator_id": operator_id,
        },
    )
    result = client.get("/api/compliance/audit-log/verify").json()
    assert result["intact"] is True
    assert result["broken_entry_ids"] == []
