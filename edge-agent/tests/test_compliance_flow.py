def test_plant_batch_lifecycle_reconciliation_and_waste(client, operator_id):
    # create an immature lot
    batch = client.post(
        "/api/compliance/plant-batches",
        json={
            "name": "TEST-2026-Clone-001",
            "batch_type": "Clone",
            "strain": "Test Strain",
            "room_id": "test-room",
            "planted_date": "2026-07-01",
            "count": 10,
            "operator_id": operator_id,
        },
    ).json()
    assert batch["untracked_count"] == 10
    assert batch["tracked_count"] == 0

    # before any physical count, reconciliation should flag the room as needing one
    recon = client.get("/api/compliance/reconciliation").json()
    row = next(r for r in recon if r["room_id"] == "test-room")
    assert row["system_count"] == 10
    assert row["needs_recount"] is True

    # tag 4 of the 10 as individually tracked plants
    tagged = client.post(
        f"/api/compliance/plant-batches/{batch['id']}/tag-plants",
        json={"count": 4, "growth_phase": "Vegetative", "operator_id": operator_id},
    ).json()
    assert tagged["batch"]["untracked_count"] == 6
    assert tagged["batch"]["tracked_count"] == 4
    assert len(tagged["plants"]) == 4
    plant_id = tagged["plants"][0]["id"]

    # tagging more than what remains untracked is rejected
    over_tag = client.post(
        f"/api/compliance/plant-batches/{batch['id']}/tag-plants",
        json={"count": 999, "operator_id": operator_id},
    )
    assert over_tag.status_code == 400

    # an unknown operator is rejected outright
    unknown_operator = client.post(
        f"/api/compliance/plant-batches/{batch['id']}/tag-plants",
        json={"count": 1, "operator_id": "op-does-not-exist"},
    )
    assert unknown_operator.status_code == 404

    # destroy one tagged plant -> waste event + batch counter update
    destroy = client.post(
        f"/api/compliance/plants/{plant_id}/destroy",
        json={
            "weight_g": 12.5, "method": "Compost", "material": "Soil", "reason": "Contamination",
            "operator_id": operator_id,
        },
    ).json()
    assert destroy["plant"]["status"] == "destroyed"
    waste_event_id = destroy["waste_event"]["id"]

    # a freshly-logged waste event should not be overdue yet
    waste_events = client.get("/api/compliance/waste-events").json()
    fresh_event = next(w for w in waste_events if w["id"] == waste_event_id)
    assert fresh_event["overdue"] is False

    # mark it reported and confirm it stays non-overdue
    marked = client.post(f"/api/compliance/waste-events/{waste_event_id}/mark-reported?operator_id={operator_id}").json()
    assert marked["reported_at"] is not None

    # audit trail recorded both the tag and destroy actions for this plant
    audit = client.get(f"/api/compliance/audit-log?entity_id={plant_id}").json()
    actions = {entry["action"] for entry in audit}
    assert {"tagged", "destroyed"}.issubset(actions)

    # record a physical count and confirm reconciliation reflects it
    physical = client.post(
        "/api/compliance/physical-counts",
        json={"room_id": "test-room", "counted_value": 9, "operator_id": operator_id},
    ).json()
    assert physical["system_value_at_time"] == 9  # 10 planted - 1 destroyed
    assert physical["discrepancy"] == 0

    recon_after = client.get("/api/compliance/reconciliation").json()
    row_after = next(r for r in recon_after if r["room_id"] == "test-room")
    assert row_after["needs_recount"] is False


def test_harvest_to_package_lineage(client, operator_id):
    harvest = client.post(
        "/api/compliance/harvests",
        json={
            "name": "TEST-HARVEST-001", "strain": "Test Strain", "source_room_id": "test-room",
            "operator_id": operator_id,
        },
    ).json()

    # duplicate harvest names are rejected, matching METRC's uniqueness requirement
    dup = client.post(
        "/api/compliance/harvests",
        json={
            "name": "TEST-HARVEST-001", "strain": "Test Strain", "source_room_id": "test-room",
            "operator_id": operator_id,
        },
    )
    assert dup.status_code == 400

    weigh_dry = client.post(
        f"/api/compliance/harvests/{harvest['id']}/weigh",
        json={"stage": "dry", "weight_g": 500.0, "room_id": "dry-room", "operator_id": operator_id},
    )
    assert weigh_dry.status_code == 200

    logs = client.get(f"/api/compliance/harvests/{harvest['id']}/weight-logs").json()
    assert any(entry["stage"] == "dry" and entry["weight_g"] == 500.0 for entry in logs)

    package = client.post(
        f"/api/compliance/harvests/{harvest['id']}/package",
        json={"item_name": "Test Flower", "weight_g": 450.0, "room_id": "vault-room", "operator_id": operator_id},
    ).json()
    assert package["harvest_id"] == harvest["id"]

    packages = client.get("/api/compliance/packages").json()
    assert any(p["id"] == package["id"] for p in packages)

    sold = client.post(
        f"/api/compliance/packages/{package['id']}/update-status",
        json={"status": "sold", "operator_id": operator_id},
    ).json()
    assert sold["status"] == "sold"

    rejected = client.post(
        f"/api/compliance/packages/{package['id']}/update-status",
        json={"status": "not-a-real-status", "operator_id": operator_id},
    )
    assert rejected.status_code == 400


def test_destroy_requires_correct_pin_when_operator_has_one(client):
    piloted = client.post("/api/operators", json={"name": "Pinned Operator", "pin": "4242"}).json()
    batch = client.post(
        "/api/compliance/plant-batches",
        json={
            "name": "PIN-TEST-001", "batch_type": "Clone", "strain": "Test Strain", "room_id": "test-room",
            "planted_date": "2026-07-01", "count": 1, "operator_id": piloted["id"],
        },
    ).json()
    tagged = client.post(
        f"/api/compliance/plant-batches/{batch['id']}/tag-plants",
        json={"count": 1, "operator_id": piloted["id"]},
    ).json()
    plant_id = tagged["plants"][0]["id"]

    missing_pin = client.post(
        f"/api/compliance/plants/{plant_id}/destroy",
        json={"weight_g": 5.0, "operator_id": piloted["id"]},
    )
    assert missing_pin.status_code == 401

    wrong_pin = client.post(
        f"/api/compliance/plants/{plant_id}/destroy",
        json={"weight_g": 5.0, "operator_id": piloted["id"], "pin": "0000"},
    )
    assert wrong_pin.status_code == 401

    correct_pin = client.post(
        f"/api/compliance/plants/{plant_id}/destroy",
        json={"weight_g": 5.0, "operator_id": piloted["id"], "pin": "4242"},
    )
    assert correct_pin.status_code == 200


def test_witness_must_be_a_different_operator(client, operator_id):
    batch = client.post(
        "/api/compliance/plant-batches",
        json={
            "name": "WITNESS-TEST-001", "batch_type": "Clone", "strain": "Test Strain", "room_id": "test-room",
            "planted_date": "2026-07-01", "count": 1, "operator_id": operator_id,
        },
    ).json()
    tagged = client.post(
        f"/api/compliance/plant-batches/{batch['id']}/tag-plants",
        json={"count": 1, "operator_id": operator_id},
    ).json()
    plant_id = tagged["plants"][0]["id"]

    self_witness = client.post(
        f"/api/compliance/plants/{plant_id}/destroy",
        json={"weight_g": 5.0, "operator_id": operator_id, "witness_operator_id": operator_id},
    )
    assert self_witness.status_code == 400

    other = client.post("/api/operators", json={"name": "Witness Operator"}).json()
    witnessed = client.post(
        f"/api/compliance/plants/{plant_id}/destroy",
        json={"weight_g": 5.0, "operator_id": operator_id, "witness_operator_id": other["id"]},
    ).json()
    assert witnessed["waste_event"]["witnessed_by"] == "Witness Operator"
