# MQTT security

`deploy/mosquitto.conf` (the default, used by `docker-compose.yml` as shipped) accepts
anonymous, unencrypted connections on port 1883 from anything that can reach the
broker: `listener 1883` / `allow_anonymous true`, no credentials, no TLS. That's fine
for a single device developing against itself, or a genuinely isolated single-Pi
deployment where nothing else is even on the network. It stops being fine the moment a
second device (a second Pi at the same site, or `master` aggregating multiple sites)
shares a network you don't fully control — anyone on that network can publish fake
sensor readings or fake audit-relay events into any site's mesh, or just read
everything, since there's nothing checking who's connecting.

The mechanism for real MQTT authentication and TLS exists and works once configured —
matching this project's usual pattern (`CANOPY_API_TOKEN`, `CANOPY_MASTER_TOKEN`):
unset means off, so local dev keeps working with zero configuration, and it becomes
real the moment you set it up. This is opt-in, not on by default, for the same reason
those other tokens are — turning it on requires you to actually generate and manage
real credentials, which isn't something to force on a local dev loop.

## Turning it on

### 1. Generate credentials

```
./scripts/generate-mqtt-credentials.sh canopy-edge-agent
./scripts/generate-mqtt-credentials.sh canopy-master
```

Run once per identity that connects to the broker — typically one per edge-agent site
plus one for `master`, though a single shared username/password also works fine if
you'd rather manage one credential instead of several (mosquitto's `password_file`
doesn't care how many identities you set up, or whether they're actually distinct).
This uses the same `eclipse-mosquitto` Docker image already pulled for the broker
itself, so nothing new needs installing locally. Writes to `deploy/passwd` by default.

### 2. (Optional) Generate a cert for TLS too

Only needed if you also want the connection encrypted, not just authenticated — the
same self-signed-cert script already used for the HTTP API's TLS option (see
`docs/deployment-tls.md`) works here too:

```
./scripts/generate-self-signed-cert.sh ./certs canopy.local
```

### 3. Switch mosquitto to the secure config

`deploy/mosquitto.secure.conf.example` requires credentials on port 1883, and adds a
TLS listener on 8883 if you generated certs. Point `docker-compose.yml`'s mosquitto
volume mount at it instead of `mosquitto.conf` (or copy it over `mosquitto.conf`
directly), and mount `deploy/passwd` and `./certs` into the container alongside it —
the example config expects them at `/mosquitto/config/passwd` and `/mosquitto/certs/`.

### 4. Point every client at the new credentials

Set on every service that connects to the broker (`edge-agent`, `master`):

```
CANOPY_MQTT_USERNAME=canopy-edge-agent
CANOPY_MQTT_PASSWORD=<the password you set>
# only if you also did step 2 and switched clients to port 8883:
CANOPY_MQTT_TLS=true
CANOPY_MQTT_CA_CERT=/path/to/certs/cert.pem
CANOPY_MQTT_PORT=8883
```

Unset `CANOPY_MQTT_USERNAME` (the default) connects anonymously, matching today's
`mosquitto.conf`. Unset `CANOPY_MQTT_TLS` (the default) connects in plaintext.

## What this does not cover

**Multi-broker bridging across sites** (a real production topology — each site running
its own local broker, bridged to a central one, rather than every site reaching one
shared broker directly) is a different, larger piece of work than credentialing a
single broker. It needs two real Mosquitto instances and real TLS certs to verify
meaningfully (the pure-Python `amqtt` broker used in this project's own local
dev/testing doesn't implement bridging at all), and hasn't been built or tested here.
The bridge directives themselves (`address`, `bridge_cafile`, `remote_username`,
`remote_password`) are standard mosquitto config if you need to set this up yourself —
see mosquitto's own bridge documentation — but nothing in this repo configures or
verifies it.

**Device pairing/registration** is still passive: a site "registers" with `master`
simply by publishing to a topic containing whatever `CANOPY_SITE_ID` it's configured
with — there's no approval step, and a valid MQTT credential is what actually gates
who can publish as any given site, not a separate pairing flow. If you're issuing one
shared credential to every device (simplest, per step 1 above), any device holding it
can publish as any site ID; issue distinct credentials per site if that distinction
matters for your deployment.
