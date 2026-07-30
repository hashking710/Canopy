# TLS

Both `edge-agent` and `master` run over plain HTTP by default — fine for local dev, and
arguably fine for a Pi on a trusted home/facility LAN nobody outside can reach. The
moment either service might be reachable beyond a network you fully trust, plaintext
HTTP means the shared-secret auth token (`CANOPY_API_TOKEN` / `CANOPY_MASTER_TOKEN`)
and every request/response — including compliance data — cross the wire readable by
anyone on the path. Pick one of the two options below before that's true.

## Option A — LAN only: uvicorn's built-in TLS with a self-signed cert

No reverse proxy, no dependencies beyond what's already installed. Browsers will show
an "untrusted certificate" warning (expected — nothing outside your LAN vouches for a
self-signed cert), but the connection is genuinely encrypted.

```
./scripts/generate-self-signed-cert.sh ./certs canopy.local
```

Then run either service with `--ssl-keyfile`/`--ssl-certfile`:

```
uvicorn canopy_agent.main:app --host 0.0.0.0 --port 8443 \
  --ssl-keyfile ./certs/key.pem --ssl-certfile ./certs/cert.pem
```

(Add `--loop none` first on Windows, per the README — unrelated to TLS, same
ProactorEventLoop issue as everywhere else in this repo.) Verified working end-to-end
against uvicorn's TLS support while building this.

Point the frontend's `VITE_API_BASE` at `https://<host>:8443` to match.

## Option B — reachable beyond your LAN: a reverse proxy with a real certificate

[Caddy](https://caddyserver.com/) is the easy path — it gets a real, trusted
Let's Encrypt certificate automatically for a real domain name, with no manual renewal.
Point a domain's DNS at your network, forward port 443, and run:

```caddyfile
canopy.example.com {
    reverse_proxy localhost:8000
}

master.example.com {
    reverse_proxy localhost:9100
}
```

That's the entire config — Caddy handles the ACME challenge, certificate issuance, and
renewal on its own. If you'd rather use nginx (e.g. it's already part of your stack),
terminate TLS there and reverse-proxy to the same local ports, with a cert from
Let's Encrypt via `certbot` or your own CA.

Either way, once a reverse proxy is doing TLS termination:

- **Update CORS.** `main.py`'s `CORSMiddleware` in both services currently allows only
  `localhost:5173` — change `allow_origins` to your real frontend origin(s) before
  anything beyond local dev depends on this.
- **The WebSocket auth token still travels as a URL query param** (`/ws/live?token=...`
  — see docs/architecture.md's Phase 3 auth section). Over HTTPS/WSS that's encrypted
  in transit same as everything else, but it can still end up in proxy/server access
  logs; be mindful of log retention/access on whatever's terminating TLS.
- **Never run Option A and B at once for the same service** — pick uvicorn's native TLS
  *or* a reverse proxy in front of a plain-HTTP uvicorn, not both layered.
