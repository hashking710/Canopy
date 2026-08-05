import base64

import pytest
from aiohttp import web
from canopy_compliancesync_metrc import MetrcComplianceSync, MetrcSyncNotImplemented

PORT = 18500


def set_env(monkeypatch, **overrides):
    env = {
        "CANOPY_METRC_VENDOR_API_KEY": "vendor-abc",
        "CANOPY_METRC_USER_API_KEY": "user-xyz",
        "CANOPY_METRC_LICENSE_NUMBER": "LIC-001",
        "CANOPY_METRC_STATE": "ok",
        "CANOPY_METRC_BASE_URL": f"http://127.0.0.1:{PORT}",
    }
    env.update(overrides)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


class RecordingServer:
    """A real local HTTP server (not a mock) that records every request it
    receives and replies 200 — the same "real local server, no live account"
    verification pattern already used by the Shelly/Ecowitt/Modbus adapters."""

    def __init__(self):
        self.requests: list[dict] = []
        self.status = 200

    async def handler(self, request: web.Request):
        body = await request.json()
        self.requests.append(
            {
                "method": request.method,
                "path": request.path,
                "query": dict(request.query),
                "headers": dict(request.headers),
                "body": body,
            }
        )
        return web.json_response({}, status=self.status)


@pytest.fixture
async def server():
    rec = RecordingServer()
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", rec.handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    await site.start()
    try:
        yield rec
    finally:
        await runner.cleanup()


def make_plant(**overrides):
    plant = {
        "id": "plant-tag-1",
        "batch_id": "batch-1",
        "strain": "GMO",
        "room_id": "greenhouse-a",
        "growth_phase": "Flowering",
        "planted_date": "2026-06-01",
        "tagged_date": "2026-07-01",
        "mother_plant_id": None,
        "status": "active",
    }
    plant.update(overrides)
    return plant


def make_waste(**overrides):
    waste = {
        "id": 1,
        "source_type": "plant",
        "source_id": "plant-tag-1",
        "room_id": "greenhouse-a",
        "waste_type": "Plant Material",
        "method": "Grinder",
        "material": "Soil",
        "reason": "Contamination",
        "weight_g": 12.5,
        "note": "n/a",
        "occurred_at": "2026-07-30T10:00:00+00:00",
    }
    waste.update(overrides)
    return waste


# ---- auth header -----------------------------------------------------------------


async def test_auth_header_is_correct_basic_auth(server, monkeypatch):
    set_env(monkeypatch)
    sync = MetrcComplianceSync()
    await sync.sync_plant_moved(make_plant(), "old-room")

    expected = base64.b64encode(b"vendor-abc:user-xyz").decode()
    assert server.requests[0]["headers"]["Authorization"] == f"Basic {expected}"


async def test_license_number_sent_as_query_param(server, monkeypatch):
    set_env(monkeypatch)
    sync = MetrcComplianceSync()
    await sync.sync_plant_moved(make_plant(), "old-room")

    assert server.requests[0]["query"] == {"licenseNumber": "LIC-001"}


# ---- plant batches -----------------------------------------------------------------


async def test_sync_plant_batch_created_real_shape(server, monkeypatch):
    set_env(monkeypatch)  # state=ok, not ca
    sync = MetrcComplianceSync()
    batch = {
        "id": "batch-1", "name": "GMO Batch 1", "batch_type": "Clone", "strain": "GMO",
        "room_id": "clone-room", "planted_date": "2026-07-01", "untracked_count": 25,
    }
    await sync.sync_plant_batch_created(batch)

    req = server.requests[0]
    assert req["method"] == "POST"
    assert req["path"] == "/plantbatches/v1/createplantings"
    assert req["body"] == [
        {
            "Name": "GMO Batch 1", "Type": "Clone", "Count": 25, "Strain": "GMO",
            "Location": "clone-room", "PatientLicenseNumber": None, "ActualDate": "2026-07-01",
        }
    ]


async def test_sync_plant_batch_created_refuses_in_california(server, monkeypatch):
    set_env(monkeypatch, CANOPY_METRC_STATE="ca")
    sync = MetrcComplianceSync()
    batch = {
        "id": "batch-1", "name": "X", "batch_type": "Clone", "strain": "GMO",
        "room_id": "clone-room", "planted_date": "2026-07-01", "untracked_count": 25,
    }
    with pytest.raises(MetrcSyncNotImplemented, match="CanCreateOpeningBalancePlantBatches"):
        await sync.sync_plant_batch_created(batch)
    assert server.requests == []  # never even attempted the call


# ---- plants -------------------------------------------------------------------------


async def test_sync_plant_tagged_real_shape(server, monkeypatch):
    set_env(monkeypatch)
    sync = MetrcComplianceSync()
    await sync.sync_plant_tagged(make_plant())

    req = server.requests[0]
    assert req["path"] == "/plants/v1/create/plantings"
    assert req["body"] == [
        {
            "PlantLabel": "plant-tag-1", "PlantBatchName": "batch-1", "PlantBatchType": "Clone",
            "PlantCount": 1, "LocationName": "greenhouse-a", "StrainName": "GMO",
            "PatientLicenseNumber": None, "ActualDate": "2026-07-01",
        }
    ]


async def test_sync_plant_moved_real_shape(server, monkeypatch):
    set_env(monkeypatch)
    sync = MetrcComplianceSync()
    await sync.sync_plant_moved(make_plant(room_id="dry-cure"), "greenhouse-a")

    req = server.requests[0]
    assert req["path"] == "/plants/v1/moveplants"
    body = req["body"][0]
    assert body["Id"] == "plant-tag-1"
    assert body["Location"] == "dry-cure"
    assert "ActualDate" in body


async def test_sync_plant_destroyed_real_shape(server, monkeypatch):
    set_env(monkeypatch)
    sync = MetrcComplianceSync()
    await sync.sync_plant_destroyed(make_plant(), make_waste())

    req = server.requests[0]
    assert req["path"] == "/plants/v1/destroyplants"
    assert req["body"] == [
        {
            "Id": "plant-tag-1", "WasteMethodName": "Grinder", "WasteMaterialMixed": "Soil",
            "WasteWeight": 12.5, "WasteUnitOfMeasureName": "Grams", "WasteReasonName": "Contamination",
            "ReasonNote": "n/a", "ActualDate": "2026-07-30",
        }
    ]


# ---- waste ------------------------------------------------------------------------


async def test_sync_waste_event_plant_source_is_a_noop_no_request(server, monkeypatch):
    """The core reason this matters: sync_plant_destroyed already reports plant
    waste via destroyplants — reporting it again here would double-count real
    destroyed material against the license's inventory."""
    set_env(monkeypatch)
    sync = MetrcComplianceSync()
    await sync.sync_waste_event(make_waste(source_type="plant"))
    assert server.requests == []


async def test_sync_waste_event_harvest_source_real_shape(server, monkeypatch):
    set_env(monkeypatch)
    sync = MetrcComplianceSync()
    await sync.sync_waste_event(make_waste(source_type="harvest", source_id="harvest-1"))

    req = server.requests[0]
    assert req["path"] == "/harvests/v1/removewaste"
    body = req["body"][0]
    assert body["Id"] == "harvest-1"
    assert body["WasteWeight"] == 12.5


async def test_sync_waste_event_package_source_raises(server, monkeypatch):
    set_env(monkeypatch)
    sync = MetrcComplianceSync()
    with pytest.raises(MetrcSyncNotImplemented, match="package"):
        await sync.sync_waste_event(make_waste(source_type="package", source_id="pkg-1"))
    assert server.requests == []


# ---- harvests -----------------------------------------------------------------------


async def test_sync_harvest_created_always_raises(server, monkeypatch):
    set_env(monkeypatch)
    sync = MetrcComplianceSync()
    with pytest.raises(MetrcSyncNotImplemented, match="harvestplants"):
        await sync.sync_harvest_created({"id": "harvest-1", "name": "H1"})
    assert server.requests == []


# ---- packages -----------------------------------------------------------------------


async def test_sync_package_created_from_harvest_real_shape(server, monkeypatch):
    set_env(monkeypatch)
    sync = MetrcComplianceSync()
    package = {
        "id": "pkg-1", "harvest_id": "harvest-1", "source_package_id": None,
        "item_name": "GMO Flower", "weight_g": 453.6, "room_id": "vault",
        "created_at": "2026-07-30T10:00:00+00:00",
    }
    await sync.sync_package_created(package)

    req = server.requests[0]
    assert req["path"] == "/harvests/v1/create/packages"
    body = req["body"][0]
    assert body["Tag"] == "pkg-1"
    assert body["Ingredients"] == [{"HarvestId": "harvest-1", "Weight": 453.6, "UnitOfWeight": "Grams"}]


async def test_sync_package_created_from_package_raises(server, monkeypatch):
    set_env(monkeypatch)
    sync = MetrcComplianceSync()
    package = {
        "id": "pkg-2", "harvest_id": None, "source_package_id": "pkg-1",
        "item_name": "GMO BHO Crude", "weight_g": 127.5, "room_id": "press",
        "created_at": "2026-07-30T10:00:00+00:00",
    }
    with pytest.raises(MetrcSyncNotImplemented, match="source_package_id"):
        await sync.sync_package_created(package)
    assert server.requests == []


# ---- error handling ----------------------------------------------------------------


async def test_non_2xx_response_raises_runtime_error(server, monkeypatch):
    set_env(monkeypatch)
    server.status = 500
    sync = MetrcComplianceSync()
    with pytest.raises(RuntimeError, match="HTTP 500"):
        await sync.sync_plant_moved(make_plant(), "old-room")


def test_plugin_metadata_is_set():
    assert MetrcComplianceSync.plugin_name == "METRC"
    assert "CANOPY_METRC_VENDOR_API_KEY" in MetrcComplianceSync.required_env_vars


def test_missing_credentials_warns_but_does_not_crash(monkeypatch, caplog):
    monkeypatch.delenv("CANOPY_METRC_VENDOR_API_KEY", raising=False)
    monkeypatch.delenv("CANOPY_METRC_USER_API_KEY", raising=False)
    monkeypatch.delenv("CANOPY_METRC_LICENSE_NUMBER", raising=False)
    with caplog.at_level("WARNING"):
        MetrcComplianceSync()
    assert "aren't all set" in caplog.text
