"""
Pushes Canopy's current sellable-inventory snapshot (services/menu_data.py) to a
Weedmaps menu.

Sourcing, so nothing here is a guess dressed up as fact (matching this codebase's own
METRC compliance-sync plugin's standard): endpoint paths, auth flow, and payload field
names below are read directly from Weedmaps' own live developer documentation at
developer.weedmaps.com (fetched, not recalled from memory) — specifically "Obtaining an
Access Token" (v2025.07), "Menu API Getting Started", the `PUT /menus/{menu_id}/items/
external/{external_id}` reference, "Cannabinoids", and the "Strains"/`GET /strains`
reference (which confirmed Weedmaps' strain object is `{id, name, updated_at}` only —
no lineage field exists anywhere in their schema, unlike an earlier version of this
plugin which sent a fabricated `lineage` field with no real counterpart).

Two things about this integration are NOT things this plugin's code can fix, and are
worth being upfront about rather than hidden behind a config error:

1. **Weedmaps' menu API is POS-partner-gated, not merchant self-serve.** Per their own
   "Onboarding Process" docs, a facility cannot get its own API credentials by signing
   up directly — access requires a company applying to become an approved
   integration/POS partner, and a menu only goes live once a dispensary explicitly
   selects that partner as its POS provider from their own Weedmaps account. As of this
   writing, Weedmaps states they are **not onboarding new integration partners**. This
   plugin is a real, correctly-shaped client ready for whenever that changes (or if
   Canopy pursues partner approval) — it is not, and structurally cannot be, a
   drop-in-your-API-key-and-go integration the way the mock/local-network adapters are.
2. Scopes/taxonomies not covered here (the exact `scope` string(s) a token needs for
   menu writes, `category`/`brand`/`tag` id taxonomies, which require an authenticated
   call to enumerate) are genuinely unconfirmed — this plugin doesn't guess at them.
"""

import logging
import os
import time
from typing import ClassVar

import aiohttp

from canopy_agent.menu_sync.base import MenuSync

logger = logging.getLogger("canopy_menusync_weedmaps")

REQUEST_TIMEOUT_SECONDS = 15
TOKEN_URL = "https://api-g.weedmaps.com/auth/token"
BASE_URL = "https://api-g.weedmaps.com/wm"
# Real tokens are documented to last 14 days — refreshed a few minutes early so a
# push mid-flight never straddles the exact expiry instant.
TOKEN_EXPIRY_SECONDS = 14 * 24 * 3600
TOKEN_REFRESH_MARGIN_SECONDS = 300

_STRAIN_TYPE_TO_GENETICS = {"indica": "indica", "sativa": "sativa", "hybrid": "hybrid"}


def _item_to_menu_item(item: dict) -> dict:
    """Maps Canopy's menu-item shape (services/menu_data.py) to Weedmaps' real
    `PUT .../menus/{menu_id}/items/external/{external_id}` request body — see this
    module's own docstring for exactly which page of developer.weedmaps.com each
    field below is read from.

    `genetics` is only included when Canopy's own strain_type maps to one of
    Weedmaps' three real enum values — an "unknown"/unset strain_type (or no linked
    strain at all) omits the field entirely rather than sending an invalid enum
    value. `lineage` has no real Weedmaps field and is not sent at all.
    """
    body: dict = {
        "name": item["item_name"],
        "variants": [
            {
                "price": {"amount": item["price_cents"] / 100, "currency": "USD"} if item.get("price_cents") else None,
                "weight": {"value": item["weight_g"], "unit": "g"} if item.get("weight_g") else None,
                "inventory_quantity": 1,
            }
        ],
    }
    genetics = _STRAIN_TYPE_TO_GENETICS.get(item.get("strain_type") or "")
    if genetics:
        body["genetics"] = genetics

    cannabinoids = []
    if item.get("thc_pct") is not None:
        cannabinoids.append({"slug": "thc", "percentage": {"min": item["thc_pct"], "max": item["thc_pct"]}})
    if item.get("cbd_pct") is not None:
        cannabinoids.append({"slug": "cbd", "percentage": {"min": item["cbd_pct"], "max": item["cbd_pct"]}})
    if cannabinoids:
        body["cannabinoids"] = cannabinoids

    return body


class WeedmapsMenuSync(MenuSync):
    """See this module's own docstring for the sourcing and the POS-partner-gating
    caveat."""

    plugin_name = "Weedmaps"
    plugin_description = (
        "Pushes current inventory/genetics/potency to a Weedmaps menu, once your "
        "facility (or the POS you use) has Weedmaps integration-partner API access — "
        "see this plugin's own module docstring for why that's a Weedmaps-side "
        "approval, not a Canopy config step."
    )
    # All facility-level, not per-room config, so all go through required_env_vars
    # (surfaced in the dashboard's credentials settings, see routers/secrets.py) —
    # same convention MetrcComplianceSync uses for its own non-secret
    # CANOPY_METRC_LICENSE_NUMBER.
    required_env_vars: ClassVar[dict[str, str]] = {
        "CANOPY_WEEDMAPS_CLIENT_ID": "Weedmaps integration-partner OAuth2 client id",
        "CANOPY_WEEDMAPS_CLIENT_SECRET": "Weedmaps integration-partner OAuth2 client secret",
        "CANOPY_WEEDMAPS_MENU_ID": "Weedmaps menu id to publish items to",
    }

    def __init__(self) -> None:
        self._client_id = os.environ.get("CANOPY_WEEDMAPS_CLIENT_ID")
        self._client_secret = os.environ.get("CANOPY_WEEDMAPS_CLIENT_SECRET")
        self._menu_id = os.environ.get("CANOPY_WEEDMAPS_MENU_ID")
        self._token_url = os.environ.get("CANOPY_WEEDMAPS_TOKEN_URL", TOKEN_URL)
        self._base_url = os.environ.get("CANOPY_WEEDMAPS_BASE_URL", BASE_URL)
        self._session: aiohttp.ClientSession | None = None
        self._token: str | None = None
        self._token_expires_at: float = 0.0

        if not (self._client_id and self._client_secret and self._menu_id):
            logger.warning(
                "WeedmapsMenuSync selected but CANOPY_WEEDMAPS_CLIENT_ID / "
                "CANOPY_WEEDMAPS_CLIENT_SECRET / CANOPY_WEEDMAPS_MENU_ID aren't all "
                "set — every push will fail until they are."
            )

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS))
        return self._session

    async def _get_token(self) -> str:
        """OAuth2 client_credentials flow — POST .../auth/token, cached for the
        documented ~14-day lifetime, refreshed a few minutes early. Fetched fresh on
        every push_menu() call only if the cached one has actually expired, not on
        every item, since one token covers the whole batch."""
        if self._token is not None and time.monotonic() < self._token_expires_at:
            return self._token

        session = self._get_session()
        async with session.post(
            self._token_url,
            json={"client_id": self._client_id, "client_secret": self._client_secret, "grant_type": "client_credentials"},
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Weedmaps token request returned HTTP {resp.status}: {text[:300]}")
            data = await resp.json()

        self._token = data["access_token"]
        expires_in = data.get("expires_in", TOKEN_EXPIRY_SECONDS)
        self._token_expires_at = time.monotonic() + expires_in - TOKEN_REFRESH_MARGIN_SECONDS
        return self._token

    async def push_menu(self, items: list[dict]) -> dict:
        if not (self._client_id and self._client_secret and self._menu_id):
            raise RuntimeError(
                "CANOPY_WEEDMAPS_CLIENT_ID / CANOPY_WEEDMAPS_CLIENT_SECRET / "
                "CANOPY_WEEDMAPS_MENU_ID must all be set — configure them via the "
                "dashboard's credentials settings before pushing to Weedmaps."
            )

        token = await self._get_token()
        session = self._get_session()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        pushed = 0
        skipped = 0
        for item in items:
            body = _item_to_menu_item(item)
            path = f"{self._base_url}/menus/{self._menu_id}/items/external/{item['package_id']}"
            try:
                async with session.put(path, json=body, headers=headers) as resp:
                    if resp.status not in (200, 201):
                        text = await resp.text()
                        raise RuntimeError(f"Weedmaps {path} returned HTTP {resp.status}: {text[:300]}")
                pushed += 1
            except Exception:
                logger.exception("failed to push package '%s' to Weedmaps — skipping it", item.get("package_id"))
                skipped += 1
        return {"pushed": pushed, "skipped": skipped}
