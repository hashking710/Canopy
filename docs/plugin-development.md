# Writing a Canopy plugin

Canopy has two extension points, both discovered the same way — via Python's standard
[entry points](https://packaging.python.org/en/latest/specifications/entry-points/)
mechanism, the same approach pytest, Flask, and Home Assistant use for their plugin
ecosystems. A plugin is a normal, independently versioned pip package that declares
itself in its own `pyproject.toml`; the core app never needs to know it exists ahead of
time, and a broken plugin can't take down the rest of the app.

- **Sensor adapters** — pull readings from a device (`canopy.sensor_adapters` group).
- **Compliance sync targets** — report compliance events to an external system like
  METRC (`canopy.compliance_sync` group).

This doc walks through a sensor adapter; a compliance sync plugin follows the identical
shape against `ComplianceSync` in `compliance_sync/base.py` instead.

## The contract

```python
# canopy_agent/adapters/base.py
class SensorAdapter(ABC):
    plugin_name: ClassVar[str] = "unnamed adapter"
    plugin_description: ClassVar[str] = ""
    config_schema: ClassVar[dict[str, str]] = {}  # descriptive only, not validated

    async def connect(self, room: Room) -> None: ...
    async def read(self, room: Room) -> dict[str, float]: ...
    async def disconnect(self, room: Room) -> None: ...
```

`read()` returns `{metric_key: value}` for whatever non-derived metrics that room's
`metric_config` expects (e.g. `temp_f`, `rh_pct`) — it doesn't need to know about VPD or
any other derived metric; the poller fills those in itself if you don't provide them.
One adapter instance is shared across every room using that `adapter_type`, so put
per-account state (a login session, a cached device list) on `self`, not per-room state.

Raise on failure — don't return partial/garbage data. The poller isolates each room's
poll in its own try/except (one failing adapter can't block readings for other rooms)
and enforces a 10s timeout on `read()` (a hung adapter can't stall the whole cycle
either), so a real exception is the correct, safe way to signal "this room didn't get a
reading this cycle."

**Credentials**: if your adapter needs an API key/token shared across every room using
it, declare it in `required_env_vars: ClassVar[dict[str, str]] = {"CANOPY_MY_DEVICE_API_KEY": "..."}`
and read it with `os.environ.get(...)` **inside `read()`, not `__init__`**. One adapter
instance is cached per `adapter_type` for the whole process lifetime (see above), so a
credential read at `__init__` time is fixed forever until a restart; reading it fresh
inside `read()` is what lets someone set/change it from the dashboard's Settings page
(`Settings` → "Sensor & sync credentials", backed by `routers/secrets.py`) and have it
take effect on the very next poll cycle. If your adapter caches an authenticated
session/token rather than re-authenticating every call, track which credential value
that session was established with and force a fresh login when it no longer matches —
see `canopy-adapter-ac-infinity`/`canopy-adapter-rainmachine` for the pattern.

**Device discovery (optional)**: if your device can be found via a local scan — BLE
(`canopy-adapter-ble`, `canopy-adapter-aranet4`) or mDNS (`canopy-adapter-shelly`) are
the two real examples — set `supports_discovery: ClassVar[bool] = True` and implement
`async def discover(cls) -> list[dict]:` returning `[{"address": ..., "name": ...}, ...]`.
The room-creation UI shows a "scan for nearby devices" button automatically for any
adapter with the flag set; leave it `False` (the default) if there's nothing to scan
for. Broadcast-based LAN discovery (mDNS/SSDP) only actually finds anything under
`docker-compose.pi.yml`'s `network_mode: host` — the default Docker bridge network
can't see real LAN multicast traffic at all, so a scan there always returns zero
results rather than erroring. See `docs/architecture.md`'s "Opt-in local-network
discovery for Pi deployments" section for the full explanation and
`canopy_adapter_shelly`'s `_scan_mdns_service`/`_format_mdns_results` split for the
"keep the live scan and the pure result-formatting separately testable" pattern to
follow. BLE discovery isn't affected by any of this — it goes through direct hardware
Bluetooth adapter access, not the container's network boundary.

## A minimal plugin package

```
canopy-adapter-my-device/
  pyproject.toml
  canopy_adapter_my_device/
    __init__.py
```

```toml
# pyproject.toml
[project]
name = "canopy-adapter-my-device"
version = "0.1.0"
dependencies = ["canopy-agent"]

[project.entry-points."canopy.sensor_adapters"]
my_device = "canopy_adapter_my_device:MyDeviceAdapter"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

```python
# canopy_adapter_my_device/__init__.py
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room


class MyDeviceAdapter(SensorAdapter):
    plugin_name = "My Device"
    plugin_description = "Polls My Device's local API for temp/RH."
    config_schema = {"host": "IP address or hostname of the device on your LAN"}

    async def connect(self, room: Room) -> None:
        pass

    async def read(self, room: Room) -> dict[str, float]:
        host = room.adapter_config["host"]
        # ... fetch and return real values ...
        return {"temp_f": 72.5, "rh_pct": 55.0}

    async def disconnect(self, room: Room) -> None:
        pass
```

`pip install -e .` it into the same venv as `edge-agent` (or `pip install
canopy-adapter-my-device` once published), set a room's `adapter_type` to `"my_device"`
and `adapter_config` to whatever `config_schema` describes, and the poller picks it up
on the next cycle — no changes to `canopy_agent` itself.

## Reference implementations

`plugins/canopy-adapter-ac-infinity/` in this repo is a complete, real example — AC
Infinity's cloud API adapter, moved out of the core app into exactly this shape. Worth
reading end to end before writing your own: it shows credential handling via env vars,
a shared cached HTTP session across rooms, and how to document what's verified vs.
reverse-engineered when you're working against an undocumented API.

A few more, each demonstrating a different situation you'll likely hit:

- **`plugins/canopy-adapter-modbus/`** — a device with no self-describing metadata
  (a register is just a number), so `adapter_config` describes the device's own
  register map instead of a fixed schema. Also a real test against a locally-run
  Modbus TCP server (`pymodbus`'s own server implementation) — real wire-protocol I/O,
  not a mock.
- **`plugins/canopy-adapter-mqtt/`** — push-based hardware (a device publishes
  whenever it wants) behind a pull-based `read()` interface: a shared background
  subscriber task caches the latest value per topic, and `read()` just returns
  whatever's cached. If your device is push-based too, this is the pattern to copy.
- **`plugins/canopy-adapter-shelly/`**, **`canopy-adapter-ecowitt/`**,
  **`canopy-adapter-switchbot/`**, **`canopy-adapter-govee/`** — each spins up a real
  local `aiohttp.web` server in its tests, implementing the vendor's actual documented
  response shape, and exercises the adapter's real HTTP request/parsing logic against
  it end to end — much stronger than mocking the HTTP client, and doesn't need a real
  device or account.
- **`plugins/canopy-adapter-gpio/`** and **`canopy-adapter-atlas-ezo/`** — real
  hardware (I2C/1-Wire/GPIO) that genuinely cannot be exercised end-to-end without a
  physical device attached to a Pi. What they do instead: every piece of pure
  protocol math (checksums, register bit-layout, sysfs text parsing) is unit-tested
  without a bus, and the docstrings say plainly what's verified vs. implemented-from-
  datasheet-but-untested. If you're writing a hardware adapter you can't test against
  real silicon either, this is the honest way to ship it — don't claim confidence you
  don't have. Also worth copying: these two lazily `import smbus2` inside the methods
  that actually touch a bus, not at module top level — `smbus2` imports the
  POSIX-only stdlib `fcntl` at import time, so importing it eagerly would break
  installing/testing the whole package on any non-Linux dev machine. GPIO's `bme280`
  kind is the sharpest example of "unverifiable but still worth shipping honestly" in
  this whole codebase — a real multi-step calibration-compensation algorithm
  implemented from memory, with tests built around what can actually be proven
  (monotonicity, edge-case guards) rather than a specific numeric answer nobody here
  can fully vouch for.
- **`plugins/canopy-adapter-tuya/`** — when a device's protocol involves real
  cryptography or custom binary framing (not just "parse these bytes"), consider
  depending on a mature real library instead of reimplementing it from memory the way
  `canopy-adapter-modbus` reimplements Modbus's own simple framing. This adapter
  depends on the real `tinytuya` PyPI package for Tuya's AES-encrypted local protocol
  — a framing/crypto bug is a worse failure mode than a wrong scale factor, since it
  can silently produce plausible-looking garbage instead of an obviously-wrong number.
  Also worth copying: before writing adapter code against a new dependency, install it
  standalone and check its real API via `inspect.signature()` rather than trusting
  memory of its interface.
- **`plugins/canopy-adapter-ble/`** — demonstrates splitting one package into two
  adapter classes (`BleAdapter` for active GATT reads, `BleAdvertisementAdapter` for
  passive broadcast scanning) when a protocol family genuinely has two different
  device models, rather than forcing both into one `read()` method. Also demonstrates
  going generic/configurable (byte offset + format per field) instead of guessing at
  one specific vendor's byte layout when real devices in the wild disagree — the same
  reasoning behind Modbus's register-map config, applied to BLE.
- **`plugins/canopy-adapter-rachio/`** and **`canopy-adapter-rainmachine/`** — a
  device family that reports control/scheduling state (`zone_active`) rather than a
  continuous sensor value; worth a look if you're adapting something that isn't
  strictly a sensor. RainMachine's tests are also a good example of testing a
  multi-step auth flow (login → token → authenticated request, with token caching
  across reads) against a real local server instead of mocking the HTTP client.

## What the core guarantees you

- **Load isolation**: if your package fails to import, or doesn't actually subclass
  `SensorAdapter`, or its entry-point name collides with an existing one, the registry
  logs it and moves on — it does not crash the app at startup. Check the edge agent's
  logs if your adapter doesn't show up in `available_adapter_types()`.
- **Per-room isolation**: an exception from your `read()` only drops that one room's
  reading for that one poll cycle; every other room keeps working.
- **A timeout**: `read()` gets 10 seconds. Design for that — if a device's API is
  sometimes slow, cache aggressively rather than blocking.

## What the core does *not* guarantee (yet)

This is in-process plugin loading (chosen over out-of-process sandboxing for lower
resource overhead on Pi-class hardware — see docs/architecture.md's Phase 2 entry for
that tradeoff). That means a plugin runs with the same permissions and the same Python
process as the rest of the app: it can access the filesystem, the network, and
everything else the edge agent can. Load-time and read-time isolation catch crashes and
hangs, not malicious or resource-abusive code. Only install plugins you trust, the same
way you'd think about any Python package before running it.
