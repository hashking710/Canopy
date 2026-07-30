import time

# A site counts as "online" if we've heard from it within this many seconds — a few
# missed edge-agent poll cycles (5s each), not just one, to tolerate a slow network hop.
ONLINE_THRESHOLD_SECONDS = 30


class Store:
    """
    In-memory mirror of the last-known state each site has published over MQTT. Not a
    system of record — each edge agent's own SQLite database owns its history; this
    just holds "what does every site look like right now" for the master panel to
    render, rebuilt for free from retained MQTT messages if the process restarts.
    """

    def __init__(self) -> None:
        self.sites: dict[str, dict[str, dict]] = {}  # site_id -> room_id -> room payload
        self.last_seen: dict[str, float] = {}  # site_id -> monotonic timestamp

    def upsert_room(self, site_id: str, room_id: str, payload: dict) -> None:
        self.sites.setdefault(site_id, {})[room_id] = payload
        self.last_seen[site_id] = time.monotonic()

    def site_summaries(self) -> list[dict]:
        now = time.monotonic()
        return [
            {
                "site_id": site_id,
                "room_count": len(rooms),
                "online": (now - self.last_seen.get(site_id, 0.0)) < ONLINE_THRESHOLD_SECONDS,
            }
            for site_id, rooms in self.sites.items()
        ]

    def rooms_for_site(self, site_id: str) -> list[dict]:
        return list(self.sites.get(site_id, {}).values())


store = Store()
