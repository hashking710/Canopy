# Screenshots

← back to [README](../README.md)

Every image below is a real screenshot of Canopy's own [live demo](https://cdemo.hkdev.run) —
seeded with realistic data (`CANOPY_DEMO_MODE=true`, see `edge-agent/canopy_agent/seed_compliance.py`),
not mocked up. Click through to the demo itself to click around live.

## Facility overview

![Facility overview — 142 tagged plants across a two-bay greenhouse, propagation, post-harvest, and solventless-extraction rooms, each with live sensor readings](screenshots/01-facility-overview.png)

Every room on site, one card each — greenhouse bays, clone/mother rooms, dry & cure,
ice-water-hash/live-rosin processing, vault storage. Temp, RH, VPD, CO2, soil moisture,
and runoff EC are pulled from whatever sensor adapter that room is actually configured
with, not typed in by hand.

## Room detail

![Room detail for greenhouse bay A — current readings, a live temp sparkline, and a scrolling history table](screenshots/02-room-detail.png)

Click into any room for a metric picker, a sparkline chart, and the raw reading history
behind it.

## Compliance

![Compliance page — chain of custody, retail rules for California with regulation citations, plant-count reconciliation, waste log, and the hash-chained audit trail](screenshots/03-compliance.png)

Jurisdiction-aware cultivation and retail rules (cited to the actual regulation
section, not summarized), plant-count reconciliation, a waste/destruction log with
real reporting deadlines, and the SHA-256 hash-chained audit trail with a
"chain intact" verifier.

## Plants & harvest — batches and tagged plants

![Plant batches and individually tagged plants tables](screenshots/04-plant-batches.png)

Plants start as an untagged, count-based batch and become individually METRC-style
tagged plants as they move to canopy — the same lifecycle real track-and-trace systems
use.

## Harvests

![Harvests page — wet/dry/cure weigh-ins and package creation from a finished harvest](screenshots/05-harvests.png)

A harvest gathers wet material from one or more plants, gets weighed at each stage,
and finishes as one or more packages.

## Packages & lab tests

![Packages table showing a BHO-extraction chain, and a lab tests table with a passing residual-solvents result and an attached certificate of analysis](screenshots/06-packages-lab-tests.png)

Packages can be processed into new packages (extraction, winterization, distillation),
with full lineage tracking. Solvent-extracted packages stay flagged until a real,
attached certificate of analysis shows a passing result for that exact batch.

## Alerts

![Alerts page — currently-breached alerts and per-room/per-metric threshold rules](screenshots/07-alerts.png)

Threshold rules per room and metric, evaluated every poll cycle, with an optional
webhook/email/Discord notification channel — see [discord-alerts.md](discord-alerts.md).

## License

![License page — open source, unlicensed, all features unlocked](screenshots/08-license.png)

Nothing is gated in the open-source build. See
[licensing-design.md](licensing-design.md) for how the corporate tier is designed to
work once it exists as a separate package.

## Settings

![Settings page — timezone and default temperature-unit preferences, and local rotating backups](screenshots/09-settings.png)

Per-device timezone/unit preferences, plus manual and automatic rotating backups with
a documented restore path. The Updates card at the bottom shows the exact commit this
install is running and checks GitHub for how far behind `main` it is, on demand.

## Master control panel

![Master control panel on a single-site facility — a friendly explainer instead of a raw fetch error](screenshots/10-master-sites.png)

A single-Pi facility isn't part of a multi-site setup, so this page explains that
plainly instead of surfacing a raw API error — see "Which setup do I need?" in the
[README](../README.md#which-setup-do-i-need).
