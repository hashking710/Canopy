"""
A real, working MenuSync implementation with no external service behind it — the
"generic POS" a facility can point CANOPY_MENU_SYNC at today, before they've picked
(or gotten API access to) a real vendor. Records every push it receives in-memory
(inspectable via `.pushes`) and logs a one-line summary per item, so wiring this up
end-to-end (menu_sync_task.py's interval, the /api/menu-sync/run "sync now" button,
genetics/potency actually flowing through from services/menu_data.py) can be
verified for real without needing a POS/Weedmaps account.
"""

import logging
from typing import ClassVar

from canopy_agent.menu_sync.base import MenuSync

logger = logging.getLogger("canopy_menusync_mock")


class MockMenuSync(MenuSync):
    plugin_name = "Mock POS/Menu (testing)"
    plugin_description = "Logs what it would push, keeps no state elsewhere — for testing the menu-sync pipeline without a real vendor account."
    required_env_vars: ClassVar[dict[str, str]] = {}

    def __init__(self) -> None:
        # Instance state, not class state — a fresh list per plugin instance (the
        # registry keeps one instance for the process lifetime, same as every
        # other sync/adapter plugin), so pushes accumulate across calls within one
        # run but don't leak across separate test processes.
        self.pushes: list[list[dict]] = []

    async def push_menu(self, items: list[dict]) -> dict:
        self.pushes.append(items)
        for item in items:
            logger.info(
                "mock menu sync: would push '%s' (%s, %s%% THC / %s%% CBD, %sg)",
                item.get("item_name"),
                item.get("strain_name") or "unknown strain",
                item.get("thc_pct"),
                item.get("cbd_pct"),
                item.get("weight_g"),
            )
        return {"pushed": len(items), "skipped": 0}
