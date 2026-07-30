import random

from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room


class MockAdapter(SensorAdapter):
    """
    Generates plausible readings with a slow bounded random walk per (room, metric),
    seeded from the min/max range in each room's metric_config, so the dashboard
    visibly drifts over time instead of sitting static. Stands in for real hardware
    until a Phase 2 adapter (AC Infinity, GPIO probes, ...) implements this same
    interface.
    """

    plugin_name = "Mock (built-in)"
    plugin_description = "Simulated readings for local development — no hardware required."

    def __init__(self) -> None:
        self._state: dict[tuple[str, str], float] = {}

    async def connect(self, room: Room) -> None:
        pass

    async def disconnect(self, room: Room) -> None:
        pass

    async def read(self, room: Room) -> dict[str, float]:
        values: dict[str, float] = {}
        for metric, cfg in room.metric_config.items():
            if cfg.get("derived"):
                continue
            if "min" not in cfg or "max" not in cfg:
                raise RuntimeError(
                    f"room '{room.id}' metric '{metric}' uses the mock adapter but its metric_config "
                    f"is missing 'min'/'max' — the mock adapter needs a range to walk within"
                )
            lo, hi = cfg["min"], cfg["max"]
            step = cfg.get("step", (hi - lo) * 0.05)
            key = (room.id, metric)
            current = self._state.get(key, (lo + hi) / 2)
            current += random.uniform(-step, step)
            current = max(lo, min(hi, current))
            self._state[key] = current
            values[metric] = current
        return values
