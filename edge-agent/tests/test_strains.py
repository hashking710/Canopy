def make_strain_body(operator_id: str, **overrides):
    body = {
        "name": "GMO",
        "lineage": "Chemdog x Girl Scout Cookies",
        "strain_type": "hybrid",
        "description": "Pungent, gassy hybrid.",
        "thc_pct_typical": 24.5,
        "cbd_pct_typical": 0.3,
        "operator_id": operator_id,
    }
    body.update(overrides)
    return body


def test_create_strain(client, operator_id):
    resp = client.post("/api/strains", json=make_strain_body(operator_id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "GMO"
    assert body["strain_type"] == "hybrid"
    assert body["thc_pct_typical"] == 24.5


def test_create_strain_requires_a_real_operator(client):
    resp = client.post("/api/strains", json=make_strain_body("op-does-not-exist"))
    assert resp.status_code == 404


def test_create_strain_rejects_viewer_role(client, operator_id):
    viewer = client.post("/api/operators", json={"name": "Just Looking", "role": "viewer"}).json()
    resp = client.post("/api/strains", json=make_strain_body(viewer["id"]))
    assert resp.status_code == 403


def test_create_strain_rejects_unknown_strain_type(client, operator_id):
    resp = client.post("/api/strains", json=make_strain_body(operator_id, strain_type="bogus"))
    assert resp.status_code == 400


def test_cannot_create_a_strain_with_a_duplicate_name(client, operator_id):
    client.post("/api/strains", json=make_strain_body(operator_id))
    resp = client.post("/api/strains", json=make_strain_body(operator_id))
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


def test_list_strains_only_returns_active(client, operator_id):
    created = client.post("/api/strains", json=make_strain_body(operator_id)).json()
    client.post(f"/api/strains/{created['id']}/deactivate", params={"operator_id": operator_id})
    assert client.get("/api/strains").json() == []


def test_update_strain(client, operator_id):
    created = client.post("/api/strains", json=make_strain_body(operator_id)).json()
    resp = client.put(
        f"/api/strains/{created['id']}",
        json={"description": "Updated notes", "thc_pct_typical": 26.0, "operator_id": operator_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] == "Updated notes"
    assert body["thc_pct_typical"] == 26.0
    assert body["name"] == "GMO"  # untouched fields survive


def test_update_strain_requires_a_real_operator(client, operator_id):
    created = client.post("/api/strains", json=make_strain_body(operator_id)).json()
    resp = client.put(f"/api/strains/{created['id']}", json={"operator_id": "op-does-not-exist"})
    assert resp.status_code == 404


def test_update_strain_rejects_viewer_role(client, operator_id):
    created = client.post("/api/strains", json=make_strain_body(operator_id)).json()
    viewer = client.post("/api/operators", json={"name": "Just Looking", "role": "viewer"}).json()
    resp = client.put(f"/api/strains/{created['id']}", json={"operator_id": viewer["id"]})
    assert resp.status_code == 403


def test_update_nonexistent_strain_is_404(client, operator_id):
    resp = client.put("/api/strains/does-not-exist", json={"operator_id": operator_id})
    assert resp.status_code == 404


def test_update_strain_rejects_unknown_strain_type(client, operator_id):
    created = client.post("/api/strains", json=make_strain_body(operator_id)).json()
    resp = client.put(
        f"/api/strains/{created['id']}", json={"strain_type": "bogus", "operator_id": operator_id}
    )
    assert resp.status_code == 400


def test_update_strain_rejects_duplicate_name(client, operator_id):
    client.post("/api/strains", json=make_strain_body(operator_id))
    other = client.post("/api/strains", json=make_strain_body(operator_id, name="Jelly Breath")).json()
    resp = client.put(f"/api/strains/{other['id']}", json={"name": "GMO", "operator_id": operator_id})
    assert resp.status_code == 400


def test_deactivate_strain_requires_a_real_operator(client, operator_id):
    created = client.post("/api/strains", json=make_strain_body(operator_id)).json()
    resp = client.post(f"/api/strains/{created['id']}/deactivate", params={"operator_id": "op-does-not-exist"})
    assert resp.status_code == 404


def test_deactivate_strain_rejects_viewer_role(client, operator_id):
    created = client.post("/api/strains", json=make_strain_body(operator_id)).json()
    viewer = client.post("/api/operators", json={"name": "Just Looking", "role": "viewer"}).json()
    resp = client.post(f"/api/strains/{created['id']}/deactivate", params={"operator_id": viewer["id"]})
    assert resp.status_code == 403


def test_deactivate_nonexistent_strain_is_404(client, operator_id):
    resp = client.post("/api/strains/does-not-exist/deactivate", params={"operator_id": operator_id})
    assert resp.status_code == 404
