def test_license_status_defaults_to_unlicensed_and_unlocked(client):
    resp = client.get("/api/license/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["tier"] == "unlicensed"
    assert body["features_unlocked"] == "all"
