def _make_harvest_package(client, operator_id, name="TEST-HARVEST-BHO", weight_g=1000.0):
    client.post(
        "/api/compliance/harvests",
        json={"name": name, "strain": "Test Strain", "source_room_id": "test-room", "operator_id": operator_id},
    )
    harvest_id = client.get("/api/compliance/harvests").json()
    harvest = next(h for h in harvest_id if h["name"] == name)
    return client.post(
        f"/api/compliance/harvests/{harvest['id']}/package",
        json={"item_name": "Trim", "weight_g": weight_g, "room_id": "test-room", "operator_id": operator_id},
    ).json()


def test_processing_a_package_creates_a_derivative_with_yield_and_lineage(client, operator_id):
    trim = _make_harvest_package(client, operator_id, weight_g=1000.0)

    crude = client.post(
        f"/api/compliance/packages/{trim['id']}/process",
        json={
            "item_name": "BHO Crude", "weight_g": 150.0, "room_id": "extraction-room",
            "process_method": "BHO Extraction", "operator_id": operator_id,
        },
    ).json()
    assert crude["source_package_id"] == trim["id"]
    assert crude["process_method"] == "BHO Extraction"
    assert crude["process_yield_pct"] == 15.0  # 150/1000 * 100

    distillate = client.post(
        f"/api/compliance/packages/{crude['id']}/process",
        json={
            "item_name": "Distillate", "weight_g": 90.0, "room_id": "extraction-room",
            "process_method": "Short-Path Distillation", "operator_id": operator_id,
        },
    ).json()
    assert distillate["source_package_id"] == crude["id"]
    assert distillate["process_yield_pct"] == 60.0  # 90/150 * 100

    # the source package is untouched by processing — still active, still there
    trim_after = next(p for p in client.get("/api/compliance/packages").json() if p["id"] == trim["id"])
    assert trim_after["status"] == "active"

    lineage = client.get(f"/api/compliance/packages/{distillate['id']}/lineage").json()
    assert [p["id"] for p in lineage] == [trim["id"], crude["id"], distillate["id"]]


def test_processing_a_nonexistent_source_package_is_404(client, operator_id):
    resp = client.post(
        "/api/compliance/packages/does-not-exist/process",
        json={"item_name": "x", "weight_g": 1, "room_id": "r", "process_method": "BHO Extraction", "operator_id": operator_id},
    )
    assert resp.status_code == 404


def test_lineage_for_a_harvest_only_package_is_a_single_entry(client, operator_id):
    trim = _make_harvest_package(client, operator_id, name="TEST-HARVEST-SINGLE")
    lineage = client.get(f"/api/compliance/packages/{trim['id']}/lineage").json()
    assert [p["id"] for p in lineage] == [trim["id"]]


def test_package_status_accepts_processed(client, operator_id):
    trim = _make_harvest_package(client, operator_id, name="TEST-HARVEST-STATUS")
    resp = client.post(
        f"/api/compliance/packages/{trim['id']}/update-status",
        json={"status": "processed", "operator_id": operator_id},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"


def test_record_and_list_lab_tests(client, operator_id):
    trim = _make_harvest_package(client, operator_id, name="TEST-HARVEST-LAB")

    test = client.post(
        f"/api/compliance/packages/{trim['id']}/lab-tests",
        json={
            "lab_name": "Test Analytics Lab", "test_type": "residual_solvents", "result": "pass",
            "thc_pct": 85.2, "tested_at": "2026-07-01", "operator_id": operator_id,
        },
    ).json()
    assert test["package_id"] == trim["id"]
    assert test["result"] == "pass"
    assert test["recorded_by"]

    listed = client.get(f"/api/compliance/packages/{trim['id']}/lab-tests").json()
    assert any(t["id"] == test["id"] for t in listed)

    all_tests = client.get("/api/compliance/lab-tests").json()
    assert any(t["id"] == test["id"] for t in all_tests)

    passing_only = client.get("/api/compliance/lab-tests?result=fail").json()
    assert not any(t["id"] == test["id"] for t in passing_only)


def test_same_day_retest_is_listed_most_recently_recorded_first(client, operator_id):
    # tested_at is a plain date — when two tests share the same date (a same-day
    # retest superseding an earlier failing result), list order must break the tie by
    # recorded_at (a real timestamp), not leave it ambiguous.
    trim = _make_harvest_package(client, operator_id, name="TEST-HARVEST-RETEST")

    first = client.post(
        f"/api/compliance/packages/{trim['id']}/lab-tests",
        json={
            "lab_name": "Lab", "test_type": "residual_solvents", "result": "fail",
            "tested_at": "2026-07-10", "operator_id": operator_id,
        },
    ).json()
    second = client.post(
        f"/api/compliance/packages/{trim['id']}/lab-tests",
        json={
            "lab_name": "Lab", "test_type": "residual_solvents", "result": "pass",
            "tested_at": "2026-07-10", "operator_id": operator_id,
        },
    ).json()

    listed = client.get(f"/api/compliance/packages/{trim['id']}/lab-tests").json()
    assert listed[0]["id"] == second["id"]
    assert listed[1]["id"] == first["id"]


def test_lab_test_rejects_an_invalid_result(client, operator_id):
    trim = _make_harvest_package(client, operator_id, name="TEST-HARVEST-BADRESULT")
    resp = client.post(
        f"/api/compliance/packages/{trim['id']}/lab-tests",
        json={
            "lab_name": "Lab", "test_type": "potency", "result": "maybe",
            "tested_at": "2026-07-01", "operator_id": operator_id,
        },
    )
    assert resp.status_code == 400


def test_lab_test_for_nonexistent_package_is_404(client, operator_id):
    resp = client.post(
        "/api/compliance/packages/does-not-exist/lab-tests",
        json={"lab_name": "Lab", "test_type": "potency", "result": "pass", "tested_at": "2026-07-01", "operator_id": operator_id},
    )
    assert resp.status_code == 404


def test_process_output_cannot_exceed_source_weight(client, operator_id):
    trim = _make_harvest_package(client, operator_id, name="TEST-HARVEST-OVERWEIGHT", weight_g=100.0)
    resp = client.post(
        f"/api/compliance/packages/{trim['id']}/process",
        json={
            "item_name": "Impossible Yield", "weight_g": 5000.0, "room_id": "extraction-room",
            "process_method": "BHO Extraction", "operator_id": operator_id,
        },
    )
    assert resp.status_code == 400
    assert "exceeds" in resp.json()["detail"]


def test_process_output_is_checked_cumulatively_across_multiple_calls(client, operator_id):
    trim = _make_harvest_package(client, operator_id, name="TEST-HARVEST-CUMULATIVE", weight_g=100.0)

    first = client.post(
        f"/api/compliance/packages/{trim['id']}/process",
        json={
            "item_name": "Crude A", "weight_g": 60.0, "room_id": "extraction-room",
            "process_method": "BHO Extraction", "operator_id": operator_id,
        },
    )
    assert first.status_code == 200

    # 60g already pulled + 60g more requested = 120g, more than the 100g source has
    second = client.post(
        f"/api/compliance/packages/{trim['id']}/process",
        json={
            "item_name": "Crude B", "weight_g": 60.0, "room_id": "extraction-room",
            "process_method": "BHO Extraction", "operator_id": operator_id,
        },
    )
    assert second.status_code == 400
    assert "40.0g" in second.json()["detail"]  # remaining unprocessed weight

    # but a request within the remaining 40g still succeeds
    third = client.post(
        f"/api/compliance/packages/{trim['id']}/process",
        json={
            "item_name": "Crude B", "weight_g": 40.0, "room_id": "extraction-room",
            "process_method": "BHO Extraction", "operator_id": operator_id,
        },
    )
    assert third.status_code == 200


def test_coa_upload_and_download_roundtrip(client, operator_id):
    trim = _make_harvest_package(client, operator_id, name="TEST-HARVEST-COA")
    test = client.post(
        f"/api/compliance/packages/{trim['id']}/lab-tests",
        json={
            "lab_name": "Test Analytics Lab", "test_type": "potency", "result": "pass",
            "tested_at": "2026-07-01", "operator_id": operator_id,
        },
    ).json()
    assert test["coa_filename"] is None

    upload = client.post(
        f"/api/compliance/lab-tests/{test['id']}/coa",
        data={"operator_id": operator_id},
        files={"file": ("coa-report.pdf", b"%PDF-1.4 fake coa bytes", "application/pdf")},
    )
    assert upload.status_code == 200
    assert upload.json()["coa_filename"] == "coa-report.pdf"

    download = client.get(f"/api/compliance/lab-tests/{test['id']}/coa")
    assert download.status_code == 200
    assert download.content == b"%PDF-1.4 fake coa bytes"
    assert download.headers["content-disposition"].endswith('filename="coa-report.pdf"') or "coa-report.pdf" in download.headers["content-disposition"]


def test_coa_upload_rejects_unsupported_file_type(client, operator_id):
    trim = _make_harvest_package(client, operator_id, name="TEST-HARVEST-COA-BADTYPE")
    test = client.post(
        f"/api/compliance/packages/{trim['id']}/lab-tests",
        json={
            "lab_name": "Lab", "test_type": "potency", "result": "pass",
            "tested_at": "2026-07-01", "operator_id": operator_id,
        },
    ).json()

    resp = client.post(
        f"/api/compliance/lab-tests/{test['id']}/coa",
        data={"operator_id": operator_id},
        files={"file": ("malware.exe", b"not a coa", "application/x-msdownload")},
    )
    assert resp.status_code == 400


def test_coa_download_404s_when_nothing_attached(client, operator_id):
    trim = _make_harvest_package(client, operator_id, name="TEST-HARVEST-COA-NONE")
    test = client.post(
        f"/api/compliance/packages/{trim['id']}/lab-tests",
        json={
            "lab_name": "Lab", "test_type": "potency", "result": "pass",
            "tested_at": "2026-07-01", "operator_id": operator_id,
        },
    ).json()
    resp = client.get(f"/api/compliance/lab-tests/{test['id']}/coa")
    assert resp.status_code == 404


def test_package_status_is_terminal_once_set(client, operator_id):
    trim = _make_harvest_package(client, operator_id, name="TEST-HARVEST-TERMINAL")

    destroyed = client.post(
        f"/api/compliance/packages/{trim['id']}/update-status",
        json={"status": "destroyed", "operator_id": operator_id},
    )
    assert destroyed.status_code == 200

    resurrect = client.post(
        f"/api/compliance/packages/{trim['id']}/update-status",
        json={"status": "active", "operator_id": operator_id},
    )
    assert resurrect.status_code == 400
    assert "final" in resurrect.json()["detail"]
