"""
Reports Canopy's compliance events to METRC's real API.

Sourcing, so nothing here is a guess dressed up as fact:
  - Auth mechanism (HTTP Basic, vendor API key + user API key, base64-encoded)
    confirmed directly against METRC's own published getting-started guide at
    api-ca.metrc.com/documentation.
  - Base URL pattern (`https://api-<state>.metrc.com`, sandbox variant
    `https://sandbox-api-<state>.metrc.com`) and every request-body field name below
    come from a real, maintained, real-world METRC integration —
    github.com/cannlytics/cannlytics-engine's `cannlytics/metrc/` client — not from
    memory. That project is already this codebase's trusted reference for METRC's
    object model (see compliance_models.py's own docstring).

Targets METRC's v1, action-based endpoints (`/plants/v1/<action>`,
`/plantbatches/v1/<action>`, `/harvests/v1/<action>`) deliberately, not v2:
California's live docs (fetched directly) confirm v2 equivalents exist for some of
these operations (`PUT /plants/v2/location`, `POST /plants/v2/waste`,
`POST /harvests/v2/packages`, `POST /plants/v2/plantings`), but nowhere accessible
without a real METRC account confirms v2's exact request-body field names. Shipping a
guessed v2 body as if it were verified would be exactly the mistake this whole
compliance module was built around catching (see docs/architecture.md's correction
history — the wrong 3-business-day waste deadline, the stale Colorado tagging
threshold, etc.). v1 is what a real, working reference client has confirmed field
shapes for; migrating to v2 once its body schema can be verified against a real
sandbox account is a mapping exercise, not a redesign — the same relationship
TrolMaster's scaffold has to a real implementation.

Every `sync_*` method below is one of two things, never a blend:
  - implemented against a confirmed shape (cited in its own docstring)
  - raises MetrcSyncNotImplemented with exactly what's still needed to finish it

`_sync()` in routers/compliance.py catches and logs any exception a compliance sync
raises — never fatal, never blocks the local record, matching every other
best-effort integration in this codebase (MQTT publish, notification channels).

"Location"/"LocationName" fields throughout are populated with Canopy's own
room_id. METRC requires this to match an already-registered Location name in your
account; if your METRC location names don't match your Canopy room ids one-to-one,
add a small room_id -> METRC location name mapping before relying on this against a
real account — not built here since there's no real account to verify the mapping
against yet.
"""

import base64
import logging
import os
from datetime import date, datetime, timezone
from typing import Any, ClassVar

import aiohttp
from canopy_agent.compliance_sync.base import ComplianceSync

logger = logging.getLogger("canopy_compliancesync_metrc")

REQUEST_TIMEOUT_SECONDS = 15


class MetrcSyncNotImplemented(Exception):
    """A compliance event with no confirmed METRC request shape yet — raised
    instead of guessing. Caught and logged by routers/compliance.py's `_sync()`,
    same as any other sync failure; never blocks the local record."""


def _iso_date(value: Any) -> str:
    """METRC's ActualDate fields want a plain 'YYYY-MM-DD', not a full timestamp.
    Every date/datetime value arriving here has already passed through
    compliance_serialize.model_to_dict(), which converts them to ISO strings before
    a sync plugin ever sees them — the date/datetime branches below are a defensive
    fallback for direct/test callers, not the normal path."""
    if isinstance(value, str):
        return value[:10]
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    return str(value)[:10]


class MetrcComplianceSync(ComplianceSync):
    """See this module's own docstring for the full sourcing/scope explanation."""

    plugin_name = "METRC"
    plugin_description = (
        "Reports plant/harvest/waste/package events to METRC over its real v1 API. "
        "Several operations are implemented against a confirmed request shape; a few "
        "(harvest creation, package-from-package processing, California plant-batch "
        "creation) aren't confirmed anywhere accessible without a real METRC account "
        "and are left unimplemented rather than guessed — see this package's docstring."
    )
    config_schema: ClassVar[dict[str, str]] = {
        "CANOPY_METRC_VENDOR_API_KEY": "Software integrator's API key",
        "CANOPY_METRC_USER_API_KEY": "This licensee's user API key",
        "CANOPY_METRC_LICENSE_NUMBER": "The facility's METRC license number",
        "CANOPY_METRC_STATE": "Two-letter state code, e.g. 'ca' (default 'ca')",
        "CANOPY_METRC_SANDBOX": "'true' to hit METRC's sandbox host instead of production",
        "CANOPY_METRC_BASE_URL": "Overrides the computed host entirely, if set",
    }

    def __init__(self) -> None:
        self._vendor_key = os.environ.get("CANOPY_METRC_VENDOR_API_KEY")
        self._user_key = os.environ.get("CANOPY_METRC_USER_API_KEY")
        self._license_number = os.environ.get("CANOPY_METRC_LICENSE_NUMBER")
        self._state = os.environ.get("CANOPY_METRC_STATE", "ca").lower()
        sandbox = os.environ.get("CANOPY_METRC_SANDBOX", "").lower() == "true"
        default_host = f"https://{'sandbox-api' if sandbox else 'api'}-{self._state}.metrc.com"
        self._base_url = os.environ.get("CANOPY_METRC_BASE_URL", default_host)
        self._session: aiohttp.ClientSession | None = None

        if not (self._vendor_key and self._user_key and self._license_number):
            logger.warning(
                "MetrcComplianceSync selected but CANOPY_METRC_VENDOR_API_KEY / "
                "CANOPY_METRC_USER_API_KEY / CANOPY_METRC_LICENSE_NUMBER aren't all "
                "set — every sync call will fail until they are."
            )

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            auth_bytes = f"{self._vendor_key}:{self._user_key}".encode()
            headers = {"Authorization": "Basic " + base64.b64encode(auth_bytes).decode()}
            self._session = aiohttp.ClientSession(
                headers=headers, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
            )
        return self._session

    async def _post(self, path: str, body: list[dict]) -> None:
        session = self._get_session()
        async with session.post(
            f"{self._base_url}{path}", json=body, params={"licenseNumber": self._license_number}
        ) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                raise RuntimeError(f"METRC {path} returned HTTP {resp.status}: {text[:300]}")

    # ---- plant batches ----------------------------------------------------------

    async def sync_plant_batch_created(self, batch: dict) -> None:
        """
        POST /plantbatches/v1/createplantings — real field shape from
        cannlytics-engine's PlantBatch.create(), whose docstring embeds a real
        example METRC payload: Name, Type, Count, Strain, Location,
        PatientLicenseNumber, ActualDate.

        California-specific: the same reference client refuses to even attempt this
        call when state == "ca", because California's own METRC configuration sets
        `CanCreateOpeningBalancePlantBatches: false` — batch creation via this
        endpoint is rejected there by design, not a bug in this plugin. Mirrored
        here rather than silently making a call METRC itself will refuse.
        """
        if self._state == "ca":
            raise MetrcSyncNotImplemented(
                "California's METRC configuration disallows plant batch creation via "
                "createplantings (CanCreateOpeningBalancePlantBatches: false) — "
                "confirmed via a real METRC client's own state-specific guard, not "
                "assumed. No known workaround for CA; batches may need to originate "
                "in METRC's own UI there."
            )
        await self._post(
            "/plantbatches/v1/createplantings",
            [
                {
                    "Name": batch["name"],
                    "Type": batch["batch_type"],
                    "Count": batch["untracked_count"],
                    "Strain": batch["strain"],
                    "Location": batch["room_id"],
                    "PatientLicenseNumber": None,
                    "ActualDate": _iso_date(batch["planted_date"]),
                }
            ],
        )

    # ---- plants -------------------------------------------------------------------

    async def sync_plant_tagged(self, plant: dict) -> None:
        """
        POST /plants/v1/create/plantings — real field shape from cannlytics-engine's
        Plant.create_planting(). PlantBatchName/PlantBatchType aren't reliably
        available here: `plant` only carries `batch_id`, a foreign key — resolving
        it to the batch's own METRC-facing name would need a DB lookup this
        interface deliberately doesn't give sync plugins access to (keeps plugins
        decoupled from the app's DB session). Falls back to the plant's own id
        rather than guessing the batch's real name.
        """
        await self._post(
            "/plants/v1/create/plantings",
            [
                {
                    "PlantLabel": plant["id"],
                    "PlantBatchName": plant.get("batch_id") or plant["id"],
                    "PlantBatchType": "Clone",
                    "PlantCount": 1,
                    "LocationName": plant["room_id"],
                    "StrainName": plant["strain"],
                    "PatientLicenseNumber": None,
                    "ActualDate": _iso_date(plant["tagged_date"]),
                }
            ],
        )

    async def sync_plant_moved(self, plant: dict, from_room_id: str) -> None:
        """POST /plants/v1/moveplants — real field shape from cannlytics-engine's
        Plant.move(). `plant["room_id"]` is already the destination by the time the
        compliance router calls this (see routers/compliance.py's move_plant); METRC's
        own shape has no "from" field to report, so from_room_id isn't sent — it's
        only relevant to Canopy's own audit trail."""
        await self._post(
            "/plants/v1/moveplants",
            [
                {
                    "Id": plant["id"],
                    "Location": plant["room_id"],
                    "ActualDate": _iso_date(datetime.now(timezone.utc)),
                }
            ],
        )

    async def sync_plant_destroyed(self, plant: dict, waste: dict) -> None:
        """POST /plants/v1/destroyplants — real field shape from cannlytics-engine's
        Plant.destroy()."""
        await self._post(
            "/plants/v1/destroyplants",
            [
                {
                    "Id": plant["id"],
                    "WasteMethodName": waste.get("method") or "Compost",
                    "WasteMaterialMixed": waste.get("material") or "Soil",
                    "WasteWeight": waste["weight_g"],
                    "WasteUnitOfMeasureName": "Grams",
                    "WasteReasonName": waste.get("reason") or "Contamination",
                    "ReasonNote": waste.get("note") or "",
                    "ActualDate": _iso_date(waste["occurred_at"]),
                }
            ],
        )

    # ---- waste ----------------------------------------------------------------------

    async def sync_waste_event(self, waste: dict) -> None:
        """
        Plant-sourced waste (source_type == "plant") is intentionally a no-op here:
        METRC's destroyplants action (see sync_plant_destroyed) already reports that
        exact waste as part of destroying the plant — METRC has no separate "waste
        event" concept for a plant source. The compliance router calls both
        sync_plant_destroyed and sync_waste_event for the same destruction (see
        routers/compliance.py), so reporting it again here would double-count real
        destroyed material against the license's inventory — a genuinely bad
        failure mode for a real regulatory system, not a cosmetic one.

        Harvest-sourced waste (source_type == "harvest") maps to
        POST /harvests/v1/removewaste — real field shape from cannlytics-engine's
        Harvest.remove_waste().

        Batch- and package-sourced waste don't have a confirmed METRC shape anywhere
        accessible without a real account, so they raise rather than guess.
        """
        source_type = waste["source_type"]
        if source_type == "plant":
            return
        if source_type == "harvest":
            await self._post(
                "/harvests/v1/removewaste",
                [
                    {
                        "Id": waste["source_id"],
                        "WasteType": waste.get("waste_type") or "Waste",
                        "UnitOfWeight": "Grams",
                        "WasteWeight": waste["weight_g"],
                        "ActualDate": _iso_date(waste["occurred_at"]),
                    }
                ],
            )
            return
        raise MetrcSyncNotImplemented(
            f"no confirmed METRC request shape for waste with source_type "
            f"'{source_type}' — only 'plant' (handled via sync_plant_destroyed) and "
            f"'harvest' (removewaste) are implemented."
        )

    # ---- harvests -----------------------------------------------------------------

    async def sync_harvest_created(self, harvest: dict) -> None:
        """
        Not implemented: METRC doesn't have a dedicated "create harvest" endpoint at
        all — a harvest batch comes into existence as a side effect of the
        `harvestplants` action on the *plants* being harvested
        (`POST /plants/v1/harvestplants`), not a standalone call. Even
        cannlytics-engine's own harvest_plants() is an unimplemented stub
        (`raise NotImplementedError`) — a real, maintained reference client
        couldn't confirm this shape either, so it isn't guessed here.
        """
        raise MetrcSyncNotImplemented(
            "METRC creates a harvest via the harvestplants action on the source "
            "plants, not a dedicated endpoint — no confirmed request shape for that "
            "action exists anywhere accessible (cannlytics-engine's own client "
            "leaves it unimplemented too); needs a real METRC sandbox account to "
            "verify before this can be built for real."
        )

    # ---- packages -------------------------------------------------------------------

    async def sync_package_created(self, package: dict) -> None:
        """
        POST /harvests/v1/create/packages — real field shape from
        cannlytics-engine's Harvest.create_package(). Only covers packages created
        directly from a harvest (package["harvest_id"] set). A package created by
        processing *another* package (package["source_package_id"] set — Canopy's
        extraction/winterization/distillation chain) needs a different METRC
        endpoint with no confirmed shape available anywhere accessible, so that path
        raises instead of guessing.
        """
        if package.get("harvest_id"):
            await self._post(
                "/harvests/v1/create/packages",
                [
                    {
                        "Tag": package["id"],
                        "Location": package["room_id"],
                        "Item": package["item_name"],
                        "UnitOfWeight": "Grams",
                        "Note": "",
                        "ActualDate": _iso_date(package["created_at"]),
                        "Ingredients": [
                            {
                                "HarvestId": package["harvest_id"],
                                "Weight": package["weight_g"],
                                "UnitOfWeight": "Grams",
                            }
                        ],
                    }
                ],
            )
            return
        raise MetrcSyncNotImplemented(
            "no confirmed METRC request shape for a package created from another "
            "package (source_package_id set, e.g. Canopy's extraction/"
            "winterization/distillation chain) — only harvest-sourced packages are "
            "implemented."
        )
