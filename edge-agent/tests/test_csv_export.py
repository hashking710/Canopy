from canopy_agent.services.csv_export import rows_to_csv


def test_rows_to_csv_empty_list_returns_empty_string():
    assert rows_to_csv([]) == ""


def test_rows_to_csv_basic():
    csv_data = rows_to_csv([{"a": "1", "b": "hello"}, {"a": "2", "b": "world"}])
    lines = csv_data.strip().splitlines()
    assert lines[0] == "a,b"
    assert lines[1] == "1,hello"
    assert lines[2] == "2,world"


def test_export_audit_log_csv(client, operator_id):
    client.post(
        "/api/compliance/plant-batches",
        json={
            "name": "CSV-TEST-001", "batch_type": "Clone", "strain": "Test Strain", "room_id": "test-room",
            "planted_date": "2026-07-01", "count": 1, "operator_id": operator_id,
        },
    )

    response = client.get("/api/compliance/export/audit-log")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    lines = response.text.strip().splitlines()
    assert lines[0] == "occurred_at,entity_type,entity_id,action,actor,room_id,details"
    assert any("plant_batch" in line and "created" in line for line in lines[1:])


def test_export_waste_events_csv(client, operator_id):
    batch = client.post(
        "/api/compliance/plant-batches",
        json={
            "name": "CSV-TEST-002", "batch_type": "Clone", "strain": "Test Strain", "room_id": "test-room",
            "planted_date": "2026-07-01", "count": 1, "operator_id": operator_id,
        },
    ).json()
    tagged = client.post(
        f"/api/compliance/plant-batches/{batch['id']}/tag-plants",
        json={"count": 1, "operator_id": operator_id},
    ).json()
    client.post(
        f"/api/compliance/plants/{tagged['plants'][0]['id']}/destroy",
        json={"weight_g": 3.5, "operator_id": operator_id},
    )

    response = client.get("/api/compliance/export/waste-events")
    assert response.status_code == 200
    lines = response.text.strip().splitlines()
    assert "3.5" in lines[1]
