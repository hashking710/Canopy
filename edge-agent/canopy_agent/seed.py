from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.models import Room


def _metric(label: str, unit: str = "", decimals: int = 1, **range_kwargs) -> dict:
    cfg = {"label": label, "unit": unit, "decimals": decimals}
    cfg.update(range_kwargs)
    return cfg


def _vpd_metric() -> dict:
    return {"label": "VPD", "unit": "kPa", "decimals": 2, "derived": "vpd"}


ROOMS: list[dict] = [
    {
        "id": "facility",
        "room_type": "facility",
        "path": "~/facility",
        "subtitle": "plants on site, right now",
        "badge": "extended-count caregiver registration",
        "footnote": "bay A: GMO · bay B: Jelly Breath · every plant METRC-tagged, immature through harvest",
        "section": "the facility",
        "sort_order": 0,
        "metric_config": {},
    },
    {
        "id": "greenhouse-a",
        "room_type": "greenhouse",
        "path": "~/greenhouse/GHA-2026-002",
        "subtitle": "greenhouse — bay A",
        "title": "GMO",
        "badge": "Flower · Day 12 · 28d To Harvest",
        "footnote": "sunrise 5:56 AM · sunset 8:16 PM · 14.3h daylight · pH 6.22",
        "section": "the greenhouse — two bays, staggered",
        "sort_order": 10,
        "tag_count": 40,
        "metric_config": {
            "temp_f": _metric("temp", "°F", 1, min=83.0, max=87.0, step=0.3),
            "rh_pct": _metric("RH", "%", 1, min=40.0, max=50.0, step=0.5),
            "vpd_kpa": _vpd_metric(),
            "co2_ppm": _metric("CO2", "ppm", 0, min=420, max=452, step=3),
            "soil_pct": _metric("soil", "%", 1, min=58, max=68, step=0.5),
            "runoff_ec": _metric("runoff EC", "", 2, min=1.4, max=1.7, step=0.03),
        },
    },
    {
        "id": "greenhouse-b",
        "room_type": "greenhouse",
        "path": "~/greenhouse/GHB-2026-003",
        "subtitle": "greenhouse — bay B",
        "title": "Jelly Breath",
        "badge": "Seedling · Day 11 · 66d To Harvest",
        "footnote": "sunrise 5:56 AM · sunset 8:16 PM · 14.3h daylight · pH 6.25",
        "section": "the greenhouse — two bays, staggered",
        "sort_order": 11,
        "tag_count": 28,
        "metric_config": {
            "temp_f": _metric("temp", "°F", 1, min=81.0, max=85.0, step=0.3),
            "rh_pct": _metric("RH", "%", 1, min=58.0, max=68.0, step=0.5),
            "vpd_kpa": _vpd_metric(),
            "co2_ppm": _metric("CO2", "ppm", 0, min=430, max=452, step=3),
            "soil_pct": _metric("soil", "%", 1, min=62, max=70, step=0.5),
            "runoff_ec": _metric("runoff EC", "", 2, min=1.4, max=1.7, step=0.03),
        },
    },
    {
        "id": "clone-room",
        "room_type": "clone_room",
        "path": "~/clone-room",
        "subtitle": "clone room",
        "title": "Oreoz",
        "badge": "100% rooted",
        "footnote": "day 14/12 · backup cuttings off the photoperiod mother lines, domed and misted",
        "section": "propagation & genetics",
        "sort_order": 20,
        "tag_count": 35,
        "metric_config": {
            "tray_count": _metric("tray count", "", 0, min=30, max=40, step=1),
            "temp_f": _metric("temp", "°F", 1, min=76.0, max=80.0, step=0.3),
            "rh_pct": _metric("RH", "%", 1, min=75.0, max=84.0, step=0.5),
        },
    },
    {
        "id": "mother-room",
        "room_type": "mother_room",
        "path": "~/mother-room",
        "subtitle": "mother / breeding room",
        "title": "Wilson × Sour Papaya",
        "badge": "Seed Development",
        "footnote": "18/6 · day 72/131 of this cross",
        "section": "propagation & genetics",
        "sort_order": 21,
        "tag_count": 39,
        "metric_config": {
            "lines_kept": _metric("lines kept", "", 0, min=10, max=15, step=1),
            "temp_f": _metric("temp", "°F", 1, min=74.0, max=77.0, step=0.3),
            "rh_pct": _metric("RH", "%", 1, min=55.0, max=65.0, step=0.5),
        },
    },
    {
        "id": "tissue-culture",
        "room_type": "tissue_culture",
        "path": "~/tissue-culture",
        "subtitle": "tissue culture / seedlings",
        "badge": "13 lines banked",
        "footnote": "subculture every 35d · genetic bank, disease-free stock",
        "section": "propagation & genetics",
        "sort_order": 22,
        "metric_config": {
            "days_since_sub": _metric("days since sub", "", 0, min=0, max=35, step=1),
            "contam_pct": _metric("contam", "%", 1, min=0.0, max=5.0, step=0.2),
            "seedling_count": _metric("seedlings", "", 0, min=8, max=16, step=1),
        },
    },
    {
        "id": "nutrient-room",
        "room_type": "nutrient_room",
        "path": "~/nutrient-room",
        "subtitle": "nutrient / ferment room",
        "title": "JADAM fish amino acid (JFA)",
        "badge": "Fermenting",
        "footnote": "day 7/10 · JADAM inputs, rotated on a standing schedule, feeds both bays",
        "section": "propagation & genetics",
        "sort_order": 23,
        "metric_config": {},
    },
    {
        "id": "cold-room",
        "room_type": "cold_room",
        "path": "~/cold-room/GHB-2026-002",
        "subtitle": "cold room / freezer",
        "title": "GMO",
        "badge": "Drawing-Down",
        "footnote": "fresh-frozen material held for the live rosin wash",
        "section": "post-harvest",
        "sort_order": 30,
        "metric_config": {
            "lb_stored": _metric("lb in storage", "", 1, min=0.0, max=2.0, step=0.1),
            "temp_f": _metric("temp", "°F", 1, min=-10.0, max=0.0, step=0.4),
            "days_stored": _metric("days stored", "", 0, min=0, max=20, step=1),
        },
    },
    {
        "id": "dry-cure",
        "room_type": "dry_cure",
        "path": "~/dry-cure/GHB-2026-002",
        "subtitle": "dry & cure room",
        "title": "GMO",
        "badge": "Curing · Day 3/18",
        "footnote": "jarred, burping on schedule",
        "section": "post-harvest",
        "sort_order": 31,
        "metric_config": {
            "temp_f": _metric("temp", "°F", 1, min=62.0, max=68.0, step=0.3),
            "rh_pct": _metric("RH", "%", 1, min=58.0, max=65.0, step=0.5),
            "dry_lb": _metric("dry lb", "", 1, min=5.0, max=12.0, step=0.2),
        },
    },
    {
        "id": "press-gmo",
        "room_type": "press",
        "path": "~/press/GMO",
        "subtitle": "wash → freeze-dry → press",
        "title": "GMO",
        "badge": "Processing",
        "footnote": "into this run's wash/press cycle",
        "section": "solventless — ice water hash & live rosin",
        "sort_order": 40,
        "metric_config": {
            "live_rosin_yield_pct": _metric("live rosin yield", "%", 1, min=65.0, max=80.0, step=1.0),
            "full_melt_g": _metric("full-melt (73-120µ)", "g", 0, min=60, max=90, step=2),
            "press_temp_f": _metric("press temp", "°F", 0, min=140, max=155, step=1),
            "press_psi": _metric("press psi", "", 0, min=1200, max=1500, step=10),
        },
    },
    {
        "id": "vault",
        "room_type": "vault",
        "path": "~/vault",
        "subtitle": "vault / secure storage",
        "badge": "3 runs on hand",
        "footnote": "last in: GMO, 106g · camera-monitored limited access area",
        "section": "solventless — ice water hash & live rosin",
        "sort_order": 41,
        "metric_config": {
            "on_hand_g": _metric("on hand", "g", 0, min=100, max=500, step=5),
            "lifetime_output_kg": _metric("lifetime output", "kg", 2, min=0.3, max=0.6, step=0.01),
        },
    },
]


def seed(db: Session) -> None:
    if db.execute(select(Room.id)).first() is not None:
        return
    for room_kwargs in ROOMS:
        db.add(Room(**room_kwargs))
    db.commit()
