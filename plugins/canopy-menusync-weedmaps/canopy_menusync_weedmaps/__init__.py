"""
Pushes Canopy's current sellable-inventory snapshot (services/menu_data.py) to
Weedmaps' menu for a given retailer/delivery location.

IMPORTANT — unlike this repo's METRC compliance-sync plugin (whose request shapes are
each cited against a real, maintained reference client), the exact endpoint path and
payload field names below are a best-effort, defensible REST shape (bearer-token auth,
JSON product array, the field names Weedmaps' own public partner documentation and
typical menu/POS-integration APIs use) — NOT verified against a real Weedmaps for
Business account, because no live API credentials exist to test against yet (see
docs/architecture.md and this plugin's config_schema). Both the endpoint path
(CANOPY_WEEDMAPS_BASE_URL / CANOPY_WEEDMAPS_MENU_PATH) and the payload shape
(`_item_to_product`) are deliberately overridable/isolated in one place so this is a
mapping exercise, not a redesign, once real API docs or a sandbox account are
available to confirm the exact shape against — same "built for real, flagged as
unverified" posture as compliance_sync's own MetrcComplianceSync took before its
shapes were confirmed.
"""

import logging
import os
from typing import ClassVar

import aiohttp

from canopy_agent.menu_sync.base import MenuSync

logger = logging.getLogger("canopy_menusync_weedmaps")

REQUEST_TIMEOUT_SECONDS = 15
DEFAULT_BASE_URL = "https://api.weedmaps.com"
DEFAULT_MENU_PATH = "/partner/v1/listings"


def _item_to_product(item: dict) -> dict:
    """Best-effort mapping from Canopy's menu-item shape (services/menu_data.py) to
    a Weedmaps product listing — see this module's own docstring for why this isn't
    cited against a confirmed real shape the way METRC's plugin is."""
    return {
        "external_id": item["package_id"],
        "name": item["item_name"],
        "category": "flower",
        "strain_name": item.get("strain_name"),
        "strain_type": item.get("strain_type"),
        "lineage": item.get("lineage"),
        "thc_percentage": item.get("thc_pct"),
        "cbd_percentage": item.get("cbd_pct"),
        "weight_grams": item.get("weight_g"),
        "price_cents": item.get("price_cents"),
    }


class WeedmapsMenuSync(MenuSync):
    """See this module's own docstring for the sourcing/confidence caveat."""

    plugin_name = "Weedmaps"
    plugin_description = (
        "Pushes current inventory/genetics/potency to a Weedmaps for Business menu. "
        "Built as a real integration, but its exact request shape is unverified "
        "against a live account — see this plugin's own module docstring."
    )
    # Both facility-level, not per-room config, so both go through required_env_vars
    # (surfaced in the dashboard's credentials settings, see routers/secrets.py) —
    # same convention MetrcComplianceSync uses for its own non-secret
    # CANOPY_METRC_LICENSE_NUMBER, rather than introducing a separate config_schema
    # mechanism nothing in this codebase actually renders for compliance/menu-sync
    # plugins (unlike SensorAdapter.config_schema, which really is per-room).
    required_env_vars: ClassVar[dict[str, str]] = {
        "CANOPY_WEEDMAPS_API_KEY": "Weedmaps for Business partner API key",
        "CANOPY_WEEDMAPS_LOCATION_ID": "Weedmaps retailer/delivery location id to publish this menu to",
    }

    def __init__(self) -> None:
        self._api_key = os.environ.get("CANOPY_WEEDMAPS_API_KEY")
        self._location_id = os.environ.get("CANOPY_WEEDMAPS_LOCATION_ID")
        self._base_url = os.environ.get("CANOPY_WEEDMAPS_BASE_URL", DEFAULT_BASE_URL)
        self._menu_path = os.environ.get("CANOPY_WEEDMAPS_MENU_PATH", DEFAULT_MENU_PATH)
        self._session: aiohttp.ClientSession | None = None

        if not self._api_key:
            logger.warning(
                "WeedmapsMenuSync selected but CANOPY_WEEDMAPS_API_KEY isn't set — "
                "every push will fail until it is."
            )

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
            self._session = aiohttp.ClientSession(
                headers=headers, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
            )
        return self._session

    async def push_menu(self, items: list[dict]) -> dict:
        if not self._api_key:
            raise RuntimeError(
                "CANOPY_WEEDMAPS_API_KEY is not set — configure it via the dashboard's "
                "credentials settings before pushing to Weedmaps."
            )

        session = self._get_session()
        pushed = 0
        skipped = 0
        for item in items:
            body = _item_to_product(item)
            try:
                async with session.post(
                    f"{self._base_url}{self._menu_path}",
                    json=body,
                    params={"location_id": self._location_id} if self._location_id else None,
                ) as resp:
                    if resp.status not in (200, 201):
                        text = await resp.text()
                        raise RuntimeError(f"Weedmaps {self._menu_path} returned HTTP {resp.status}: {text[:300]}")
                pushed += 1
            except Exception:
                logger.exception("failed to push package '%s' to Weedmaps — skipping it", item.get("package_id"))
                skipped += 1
        return {"pushed": pushed, "skipped": skipped}
