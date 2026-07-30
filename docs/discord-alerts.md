# Discord alerts

Canopy can post threshold-alert notifications (the same events `/alerts` shows in the
dashboard) directly into a Discord channel — your own, private server, not any shared
"Canopy community" Discord. This is a per-deployment integration you opt into, not a
hosted service: nothing leaves your own edge agent except the HTTP request straight to
Discord's webhook endpoint.

Off by default, matching this project's usual pattern (`CANOPY_API_TOKEN`,
`CANOPY_MQTT_USERNAME`, etc.): unset means off, so nothing changes until you set it up.

## Turning it on

### 1. Create a Discord incoming webhook

In your Discord server: **Server Settings → Integrations → Webhooks → New Webhook**.
Pick the channel you want alerts posted to, then copy the webhook URL.

### 2. Point Canopy at it

```bash
CANOPY_ALERT_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/<id>/<token>
```

Set this on the edge agent (in `docker-compose.yml`'s `edge-agent` service, or in your
shell/`.env` when running it directly). Every alert that fires from a room's threshold
rules (see `/alerts` in the dashboard) now also posts to that channel as a Discord
embed: which room, which metric, the threshold and current value, severity, and when
it triggered.

## Combining with other channels

Discord isn't exclusive — `CANOPY_ALERT_WEBHOOK_URL` (a generic JSON webhook, e.g. for
Slack or a custom endpoint) and `CANOPY_ALERT_SMTP_HOST`/`CANOPY_ALERT_EMAIL_*` (email)
can all be configured at the same time; every configured channel gets every alert
independently. See `docs/architecture.md` for the full alerting design and
`canopy_agent/notifications/registry.py` for how channels are discovered.

## What this does not cover

This posts **your own facility's alerts to your own Discord** — it has nothing to do
with the separate `canopy-community-bot` project (Canopy's own support/community
Discord bot), which doesn't see or relay any private facility data at all.
