import json
import logging
import os

import aiomqtt

logger = logging.getLogger("canopy_agent.mqtt")

SITE_ID = os.environ.get("CANOPY_SITE_ID", "site-1")
MQTT_HOST = os.environ.get("CANOPY_MQTT_HOST")
MQTT_PORT = int(os.environ.get("CANOPY_MQTT_PORT", "1883"))

# Unset means no auth/TLS, matching CANOPY_API_TOKEN elsewhere — local dev against the
# default anonymous-listener mosquitto.conf keeps working with zero configuration. Set
# these once deploy/mosquitto.secure.conf.example (or your own equivalent) is actually
# in use — see docs/mqtt-security.md.
MQTT_USERNAME = os.environ.get("CANOPY_MQTT_USERNAME")
MQTT_PASSWORD = os.environ.get("CANOPY_MQTT_PASSWORD")
MQTT_TLS = os.environ.get("CANOPY_MQTT_TLS", "false").lower() in ("1", "true", "yes")
MQTT_CA_CERT = os.environ.get("CANOPY_MQTT_CA_CERT")


def mqtt_enabled() -> bool:
    return bool(MQTT_HOST)


def mqtt_connect_kwargs() -> dict:
    """Auth/TLS kwargs shared by every aiomqtt.Client(...) call in this process —
    edge-agent's own publisher and its audit-relay publisher/subscriber all connect to
    the same broker with the same credentials, so this is the one place that decides
    how. (master is a separate package/deployment and keeps its own copy — see
    canopy_master/mqtt_subscriber.py.)"""
    kwargs: dict = {}
    if MQTT_USERNAME:
        kwargs["username"] = MQTT_USERNAME
        kwargs["password"] = MQTT_PASSWORD
    if MQTT_TLS:
        kwargs["tls_params"] = aiomqtt.TLSParameters(ca_certs=MQTT_CA_CERT)
    return kwargs


async def publish_states(room_payloads: list[dict]) -> None:
    """
    Publish each room's current state as a retained message on
    canopy/{site_id}/{room_id}/state, so a master aggregator gets the last-known state
    immediately on subscribe even if it wasn't connected when a value last changed.

    A fresh connection is opened per call (once per poll cycle) rather than held open
    persistently — simpler to reason about than a long-lived client's reconnect/keepalive
    state, and cheap enough at a 5s poll interval. This is entirely optional: if
    CANOPY_MQTT_HOST isn't set, or the broker is unreachable, this must never affect
    local operation — readings are already persisted and broadcast to the local
    dashboard before this is called.
    """
    if not mqtt_enabled():
        return
    try:
        async with aiomqtt.Client(
            hostname=MQTT_HOST, port=MQTT_PORT, identifier=f"canopy-{SITE_ID}", **mqtt_connect_kwargs()
        ) as client:
            for payload in room_payloads:
                topic = f"canopy/{SITE_ID}/{payload['id']}/state"
                await client.publish(topic, payload=json.dumps(payload), retain=True)
    except Exception:
        logger.warning("mqtt publish failed this cycle; continuing in local-only mode", exc_info=True)
