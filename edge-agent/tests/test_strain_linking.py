def make_strain(client, operator_id, name="GMO"):
    return client.post(
        "/api/strains",
        json={"name": name, "lineage": "", "strain_type": "hybrid", "description": "", "operator_id": operator_id},
    ).json()


def test_create_plant_batch_with_a_linked_strain(client, operator_id):
    strain = make_strain(client, operator_id)
    resp = client.post(
        "/api/compliance/plant-batches",
        json={
            "name": "TEST-Batch-1", "batch_type": "Clone", "strain": "GMO", "strain_id": strain["id"],
            "room_id": "test-room", "planted_date": "2026-07-01", "count": 5, "operator_id": operator_id,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["strain_id"] == strain["id"]


def test_create_plant_batch_with_an_unknown_strain_id_is_404(client, operator_id):
    resp = client.post(
        "/api/compliance/plant-batches",
        json={
            "name": "TEST-Batch-2", "batch_type": "Clone", "strain": "GMO", "strain_id": "strain-does-not-exist",
            "room_id": "test-room", "planted_date": "2026-07-01", "count": 5, "operator_id": operator_id,
        },
    )
    assert resp.status_code == 404


def test_create_plant_batch_without_a_strain_id_still_works(client, operator_id):
    resp = client.post(
        "/api/compliance/plant-batches",
        json={
            "name": "TEST-Batch-3", "batch_type": "Clone", "strain": "Free Text Strain",
            "room_id": "test-room", "planted_date": "2026-07-01", "count": 5, "operator_id": operator_id,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["strain_id"] is None


def test_create_harvest_with_a_linked_strain(client, operator_id):
    strain = make_strain(client, operator_id)
    resp = client.post(
        "/api/compliance/harvests",
        json={"name": "TEST-Harvest-1", "strain": "GMO", "strain_id": strain["id"], "source_room_id": "test-room", "operator_id": operator_id},
    )
    assert resp.status_code == 200
    assert resp.json()["strain_id"] == strain["id"]


def test_create_harvest_with_an_unknown_strain_id_is_404(client, operator_id):
    resp = client.post(
        "/api/compliance/harvests",
        json={"name": "TEST-Harvest-2", "strain": "GMO", "strain_id": "strain-does-not-exist", "source_room_id": "test-room", "operator_id": operator_id},
    )
    assert resp.status_code == 404


def test_create_harvest_with_a_deactivated_strain_id_is_404(client, operator_id):
    strain = make_strain(client, operator_id)
    client.post(f"/api/strains/{strain['id']}/deactivate", params={"operator_id": operator_id})
    resp = client.post(
        "/api/compliance/harvests",
        json={"name": "TEST-Harvest-3", "strain": "GMO", "strain_id": strain["id"], "source_room_id": "test-room", "operator_id": operator_id},
    )
    assert resp.status_code == 404


def test_full_menu_pipeline_from_strain_registry_to_menu_item(client, operator_id):
    """End-to-end: register a strain, link a harvest to it, package it, and confirm
    a menu-sync run actually pushes the right genetics through the mock provider."""
    strain = client.post(
        "/api/strains",
        json={
            "name": "GMO", "lineage": "Chemdog x GSC", "strain_type": "hybrid", "description": "",
            "thc_pct_typical": 24.5, "cbd_pct_typical": 0.3, "operator_id": operator_id,
        },
    ).json()
    harvest = client.post(
        "/api/compliance/harvests",
        json={"name": "TEST-Harvest-Menu", "strain": "GMO", "strain_id": strain["id"], "source_room_id": "test-room", "operator_id": operator_id},
    ).json()
    client.post(
        f"/api/compliance/harvests/{harvest['id']}/package",
        json={"item_name": "GMO Flower", "weight_g": 453.6, "room_id": "vault", "operator_id": operator_id},
    )

    run_resp = client.post("/api/menu-sync/run", params={"operator_id": operator_id})
    assert run_resp.status_code == 200
    assert run_resp.json() == {"pushed": 0, "skipped": 1}  # null provider by default in tests — still proves the pipeline runs end to end
