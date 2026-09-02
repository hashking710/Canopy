# Corporate-tier licensing — design, built end-to-end except deployment

Scope for the "paywall corporations (3+ Pis), keep it offline-capable, don't publish
how it works" ask. All three pieces now exist and are tested — the open-source
interface (this repo), the closed-source client (`../canopy-license`), and the
check-in service (`../canopy-license-server`) — see "Sizing" for exactly what each
covers. What's left is entirely operational, not code: real hosting, a real
production keypair, and a secrets manager to hold it. Two architecture decisions were
locked in early:

- The check itself lives in a **separate closed-source package**, not in this
  (open-source) repo — the only way to keep the mechanism non-public while the rest of
  Canopy stays open source, since anyone can read a public repo's source.
- Enforcement is **offline for everyone**, with a **periodic check-in required only
  for the 3+ device tier** — free/small deployments never need connectivity for this;
  paid deployments already need some connectivity for the cross-device relay anyway
  (see `docs/architecture.md`'s "Cross-device relay" section), so piggybacking a
  license check-in on that isn't a new burden.

## Restating the honest limit, briefly

Covered in depth earlier in this project's history — repeating only the conclusion,
since it shapes every decision below: no check running on hardware the customer
physically owns and controls can be made impossible to bypass. A sufficiently
motivated customer with root access can always patch out a call to
`is_feature_unlocked()`. This design does not try to prevent that. It aims for three
achievable things instead: (1) make forging a *valid signed license* require a private
key that's never shipped to any customer, (2) make casual/accidental over-deployment
(not malicious — just "we added a third Pi and didn't think about it") self-correct
via visibility, not a hard wall, and (3) give Canopy real detection and a commercial
lever (an invoice, an upgrade conversation) when the pattern looks like deliberate
abuse — a *response* capability, not a *prevention* one.

## Why "open source but paywalled" isn't a contradiction here

The gate is an **add-on**, not a **crippling of the open core**. The public repo
defines a `LicenseGate` interface (same entry-points plugin pattern already used for
`SensorAdapter`/`ComplianceSync`/`NotificationChannel`) with a default implementation
that **always returns unlocked**. Nothing in the open-source codebase is gated unless
the separate closed-source package is installed. Anyone who clones this repo and builds
it themselves gets a fully-functional system, corporate features included — same
position as GitLab CE, Elastic's open code, etc. What Canopy actually sells is hardware
pre-loaded with the closed package installed, plus the hosted check-in service, plus
support — the relationship, not a flag flip. This is worth stating plainly because it
resolves a real tension: an "open source" project whose own core code lies about
whether a feature is unlocked would be a different, worse thing than this.

## What gets gated

The natural boundary is the feature that only matters once you have multiple devices
in the first place: **the cross-device relay** (`services/audit_relay.py`, built this
session) and everything that depends on multi-device coordination — eventually the
site-server/master-brain aggregation tier described earlier. A 1-2 device deployment
never needed the relay anyway, so gating it isn't an artificial restriction on top of
otherwise-equivalent functionality — it's gating exactly the part of the system whose
value scales with device count. Environment monitoring, alerting, and compliance
tracking (including the home-grow/medical tracking, which is explicitly meant to serve
small/individual growers) stay fully unlocked at every tier.

**Follow-up required, not yet done**: `audit_relay.py` currently has no gate check at
all — it was built and wired in before this design existed. Once `canopy_agent/
licensing/` exists, `publish_pending_audit_events` and `subscribe_relay_forever` need a
`get_license_gate().is_feature_unlocked("cross_device_relay")` check, failing toward
"relay silently does nothing" (never toward corrupting local compliance data) when
locked.

## Device counting and license scope

**Decided: per-customer.** A license is scoped to a **customer**, not a single site —
a customer running two single-Pi sites (2 devices total) is still under the free-tier
line; the threshold is about a customer's overall scale, not any one facility.
`max_devices` for the default free tier is 2, matching "3+ Pis" as the stated
corporate line. The check-in service (below) tracks distinct hardware IDs per
`customer_id` across every site that customer operates, not per-site.

## License format

A signed, offline-verifiable blob:

```json
{
  "license_id": "lic_8f2a...",
  "customer_id": "cust_4b91...",
  "tier": "corporate",
  "max_devices": 10,
  "issued_at": "2026-08-01T00:00:00Z",
  "expires_at": "2027-08-01T00:00:00Z",
  "signature": "<Ed25519 signature over the above, base64>"
}
```

- **Ed25519** (via Python's `cryptography` library) — small, fast, well-supported.
  The **public** key ships baked into the closed-source `canopy-license` package;
  the **private** key exists only in Canopy's own license-issuing process, never on
  any customer's device. This is the actual security property: forging a valid
  license requires that private key, regardless of whether anyone can read the
  verification code — true whether the check is open or closed source (Kerckhoffs's
  principle), which is also why "don't disclose how it works" buys less than it
  sounds like it does.
- `expires_at` forces periodic renewal even for a customer who never runs the
  check-in client (e.g. air-gapped site) — a manual re-issue process, not a hard
  requirement to phone home, so a genuinely offline corporate deployment stays
  possible, just with a manual renewal step instead of an automatic one.
- Delivered as a `.lic` file the customer places at a configured path (env var,
  e.g. `CANOPY_LICENSE_FILE`).

## Hardware binding

Each device computes a stable hardware identifier at first activation (Pi's CPU serial
— readable from `/proc/cpuinfo` / `/sys/firmware/devicetree/base/serial-number` on
Linux; **unverified against real hardware, same caveat as everything else in this
project that needs a real Pi**) and registers it against the license via the check-in
service on first connect. This is what actually constrains "how many distinct devices
are using this license" — a single offline device has no way to know how many siblings
exist, so counting genuinely requires *some* coordination point once the answer needs
to be "more than one."

## Check-in service (new, small, not yet built)

A minimal hosted service Canopy runs — not part of either existing edge-agent or
master:

- `POST /checkin` — device presents `license_id` + `hardware_id`; service records the
  timestamp and returns current status (`ok`, `over_limit`, `revoked`).
- Server-side tracks distinct `hardware_id`s seen per `license_id` in a rolling window
  and flags (does not silently hard-block) when a license is running more devices than
  `max_devices` — surfaced to Canopy for a commercial conversation, not an automatic
  cutoff.
- **Grace period, not a cliff — decided: 30 days.** A corporate-tier device that can't
  reach check-in (network down, service outage) keeps working normally for a full
  month before anything changes — matches typical SaaS grace-period norms, and gives
  real slack for the intermittent-uplink sites this whole relay design was built to
  tolerate in the first place. Even past that window, the gate should disable only the
  corporate-tier features (relay, future aggregation) — never core single-device
  sensor/compliance function. A compliance-tracking device that hard-locks mid-harvest
  because of a network blip would be a real operational and legal problem for the
  customer, not just an inconvenience; failing toward "core function keeps working" is
  a hard requirement, not a nicety.

**Decided: Canopy self-hosts the check-in service** on a cloud provider (a small
VPS/PaaS app running the check-in API), with the Ed25519 private key held in a proper
secrets manager/KMS — never in a config file, never on a customer-facing machine.
Issuing a license is a controlled action against that key, run only from Canopy's own
infrastructure. If that key is ever compromised, every license issued under it —
past and future — needs re-issuing under a new key; the secrets-manager approach
exists specifically to make that scenario as unlikely as practical.

## Package layout (once built)

```text
canopy-license/                   (separate PRIVATE repo — not this monorepo)
  canopy_license/
    gate.py                       # implements the open LicenseGate interface
    license_format.py             # Ed25519 sign/verify, the public key baked in
    hardware_id.py                # reads this Pi's stable hardware ID
    checkin.py                    # periodic HTTPS client + grace-period state machine
  tools/issue_license.py          # vendor-side CLI, uses the private key — never shipped
  pyproject.toml                  # [project.entry-points."canopy.license_gate"]

edge-agent/canopy_agent/licensing/    (THIS repo, open source — BUILT)
  base.py                         # LicenseGate ABC: is_feature_unlocked(), status()
  registry.py                     # same entry-points pattern as adapters/registry.py;
                                   # defaults to AlwaysUnlockedGate if nothing installed
  null_gate.py                    # AlwaysUnlockedGate
routers/license.py                # GET /api/license/status — BUILT, surfaces tier/
                                   # gate/features, never hidden
```

## Sizing / what's actually a small vs. big lift

- **Built**: the open-source `licensing/` interface — `LicenseGate` ABC,
  `registry.py` (entry-points discovery under group `canopy.license_gate`, falling
  back to `AlwaysUnlockedGate` if nothing is installed *or* if what's installed is
  broken — a plugin bug fails toward everything staying unlocked, never toward
  bricking a customer's compliance tracking, same philosophy as every other plugin
  registry in this codebase), `AlwaysUnlockedGate` itself, and
  `GET /api/license/status`. `services/audit_relay.py` now gates both
  `publish_pending_audit_events` and `subscribe_relay_forever` on
  `is_feature_unlocked("cross_device_relay")` — with no `canopy-license` package
  installed, this is always `True`, so the relay behaves exactly as it did before
  licensing existed for every deployment that hasn't opted into gating. 9 new tests
  (`test_licensing_registry.py`, `test_license_status_endpoint.py`, plus one new
  case in `test_audit_relay.py`), verified live via `GET /api/license/status` against
  the running Docker container.
- **Also built**: the closed-source package itself, at `../canopy-license` (a sibling
  repo, not inside this one — deliberately, per the design above). Ed25519 sign/verify
  (`license_format.py`), hardware ID with a real-Pi-path-plus-dev-fallback
  (`hardware_id.py`), a check-in client with the 30-day grace period
  (`checkin.py`), and `CanopyLicenseGate` tying them together (`gate.py`), plus
  `tools/generate_keypair.py` and `tools/issue_license.py` for vendor-side issuing.
  37 tests — including tamper detection (signature bytes, and license *data* edited
  after signing), expiry ordering (checked only after signature verification, so a
  forged-but-far-future-dated license still fails), and real HTTP-level check-in
  behavior via `httpx.MockTransport` (success, `over_limit`, server error, connection
  error — none of which raise). Two real Python late-binding bugs were caught by these
  tests and fixed (`load_state`/`save_state`/`load_public_key` had default arguments
  bound to a module constant at *def-time*, which silently ignored later monkeypatches
  — fixed by resolving the constant inside the function body instead). Verified
  end-to-end for real: generated an actual keypair, issued an actual signed license,
  installed the package into the edge-agent's real venv, confirmed
  `canopy.license_gate` entry-point discovery finds `CanopyLicenseGate` over the
  default `AlwaysUnlockedGate`, and confirmed a real license file correctly unlocks
  `cross_device_relay` only once a simulated check-in lands — then uninstalled it
  again so the edge-agent dev environment's default stays unlicensed/unlocked, matching
  what a real customer who hasn't bought the closed package gets.
- **Also built**: the check-in service itself, at `../canopy-license-server` (another
  sibling repo — a distinct deployable service from `canopy-license`, same reasoning as
  `master` being separate from `edge-agent` in the main Canopy repo). `POST /checkin`
  (no auth — a device authenticates implicitly by presenting a real `license_id`) looks
  up the license in this service's own registry (populated by a separate
  `POST /admin/licenses` step after `tools/issue_license.py` signs one — deliberately
  not automatic, so the signing step never needs network access to this service), then
  counts distinct hardware IDs that checked in for that customer within the last 30
  days (matching the device-side grace period) and returns `over_limit` — a *signal*,
  never a rejection, still 200 OK — once that count exceeds `max_devices`. Admin
  endpoints require `CANOPY_LICENSE_SERVER_ADMIN_TOKEN`, with no "unset means open"
  default, unlike edge-agent/master's optional LAN-appliance auth — this is a hosted
  service touching customer/billing data. 25 tests (grew from the original 19 as the
  `/admin/licenses/issue` auto-issue endpoint was added). Verified for real, not just against
  `TestClient`: ran the actual service with `uvicorn`, registered a license over real
  HTTP, then ran `canopy_license`'s real (non-mocked) check-in client against it three
  times with three different hardware IDs on a 2-device license — the third genuinely
  came back `over_limit` from the live server.
- **Also built, since this doc was first written**: a real, non-placeholder Ed25519
  production keypair exists — `canopy-license`'s `CANOPY_PUBLIC_KEY_HEX` and
  `canopy-license-server`'s `CANOPY_PRIVATE_KEY_HEX` were cryptographically verified
  (an actual sign/verify round-trip, not a string comparison) to be a real matching
  pair, not the placeholder. `canopy-license-server` also gained a
  `POST /admin/licenses/issue` endpoint (auto-issues + registers a license in one
  call, rather than requiring `tools/issue_license.py` run separately then
  `POST /admin/licenses`) and a Stripe-driven auto-issue path wired from
  `canopy-website`, plus a merged local docker-compose stack alongside
  `canopy-website`/`canopy-community-bot`/a demo instance and Caddy — none of which
  this doc described when first written. The website half (`canopy.hkdev.run`) is
  live and reachable. **Still not done**: the check-in service's own public domain
  (`canopyapi.hkdev.run`) has no DNS pointed at it yet, so devices in the field can't
  reach it even though the service itself works (verified locally); secrets
  (`CANOPY_PRIVATE_KEY_HEX`, the admin token, Stripe/Resend/Discord keys) still live
  in a plaintext `.env` on the server rather than a real secrets manager/KMS as this
  doc originally called for — flagged, not yet migrated.

## Decisions log

All three open questions from the first draft of this doc are now resolved:
per-customer device counting, a 30-day check-in grace period, and a self-hosted
check-in service with the private key in a secrets manager. Nothing left undecided
at the design level — remaining work is the actual build (see "Sizing" above): the
open-source interface first, then the closed-source package, key-generation tooling,
and the check-in service itself.
