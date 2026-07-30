def test_get_facility_404_before_setup(client):
    resp = client.get("/api/facility")
    assert resp.status_code == 404
    assert "not seeded" in resp.json()["detail"]


def test_create_facility(client):
    resp = client.post("/api/facility", json={"title": "My Facility", "section": "the facility"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "facility"
    assert body["room_type"] == "facility"
    assert body["title"] == "My Facility"


def test_facility_is_gettable_after_creation(client):
    client.post("/api/facility", json={})
    resp = client.get("/api/facility")
    assert resp.status_code == 200
    assert resp.json()["id"] == "facility"


def test_cannot_create_a_second_facility(client):
    client.post("/api/facility", json={})
    resp = client.post("/api/facility", json={})
    assert resp.status_code == 400
    assert "already configured" in resp.json()["detail"]


def test_create_facility_uses_sensible_defaults(client):
    resp = client.post("/api/facility", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["subtitle"] == "plants on site, right now"
