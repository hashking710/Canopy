def _tagged_plant(client, operator_id, batch_name="WEIGHT-TEST-BATCH"):
    batch = client.post(
        "/api/compliance/plant-batches",
        json={
            "name": batch_name, "batch_type": "Clone", "strain": "Test Strain", "room_id": "test-room",
            "planted_date": "2026-07-01", "count": 2, "operator_id": operator_id,
        },
    ).json()
    tagged = client.post(
        f"/api/compliance/plant-batches/{batch['id']}/tag-plants",
        json={"count": 1, "operator_id": operator_id},
    ).json()
    return tagged["plants"][0]["id"]


def test_destroying_a_plant_rejects_a_negative_or_zero_weight(client, operator_id):
    plant_id = _tagged_plant(client, operator_id)
    negative = client.post(f"/api/compliance/plants/{plant_id}/destroy", json={"weight_g": -5.0, "operator_id": operator_id})
    assert negative.status_code == 422
    zero = client.post(f"/api/compliance/plants/{plant_id}/destroy", json={"weight_g": 0, "operator_id": operator_id})
    assert zero.status_code == 422


def test_weighing_a_harvest_rejects_a_negative_or_zero_weight(client, operator_id):
    harvest = client.post(
        "/api/compliance/harvests",
        json={"name": "WEIGHT-TEST-HARVEST", "strain": "Test Strain", "source_room_id": "test-room", "operator_id": operator_id},
    ).json()
    resp = client.post(
        f"/api/compliance/harvests/{harvest['id']}/weigh",
        json={"stage": "wet", "weight_g": -1.0, "room_id": "test-room", "operator_id": operator_id},
    )
    assert resp.status_code == 422


def test_packaging_a_harvest_rejects_a_zero_weight(client, operator_id):
    harvest = client.post(
        "/api/compliance/harvests",
        json={"name": "WEIGHT-TEST-PKG", "strain": "Test Strain", "source_room_id": "test-room", "operator_id": operator_id},
    ).json()
    resp = client.post(
        f"/api/compliance/harvests/{harvest['id']}/package",
        json={"item_name": "Flower", "weight_g": 0, "room_id": "test-room", "operator_id": operator_id},
    )
    assert resp.status_code == 422


def test_logging_waste_rejects_a_negative_weight(client, operator_id):
    harvest = client.post(
        "/api/compliance/harvests",
        json={"name": "WEIGHT-TEST-WASTE", "strain": "Test Strain", "source_room_id": "test-room", "operator_id": operator_id},
    ).json()
    resp = client.post(
        "/api/compliance/waste",
        json={
            "source_type": "harvest", "source_id": harvest["id"], "room_id": "test-room",
            "waste_type": "Fibrous", "weight_g": -10.0, "operator_id": operator_id,
        },
    )
    assert resp.status_code == 422


def test_processing_a_package_rejects_a_zero_weight(client, operator_id):
    harvest = client.post(
        "/api/compliance/harvests",
        json={"name": "WEIGHT-TEST-PROCESS", "strain": "Test Strain", "source_room_id": "test-room", "operator_id": operator_id},
    ).json()
    package = client.post(
        f"/api/compliance/harvests/{harvest['id']}/package",
        json={"item_name": "Trim", "weight_g": 100.0, "room_id": "test-room", "operator_id": operator_id},
    ).json()
    resp = client.post(
        f"/api/compliance/packages/{package['id']}/process",
        json={"item_name": "Crude", "weight_g": 0, "room_id": "test-room", "process_method": "BHO Extraction", "operator_id": operator_id},
    )
    assert resp.status_code == 422


def test_creating_a_plant_batch_rejects_a_zero_count(client, operator_id):
    resp = client.post(
        "/api/compliance/plant-batches",
        json={
            "name": "WEIGHT-TEST-ZEROCOUNT", "batch_type": "Clone", "strain": "Test Strain", "room_id": "test-room",
            "planted_date": "2026-07-01", "count": 0, "operator_id": operator_id,
        },
    )
    assert resp.status_code == 422


def test_physical_count_of_zero_is_still_allowed(client, operator_id):
    # Unlike weight/count-to-tag, a physical count of zero plants in a room is a real,
    # valid observation — must not be rejected the same way a zero weight/tag-count is.
    resp = client.post(
        "/api/compliance/physical-counts",
        json={"room_id": "test-room", "counted_value": 0, "operator_id": operator_id},
    )
    assert resp.status_code == 200
