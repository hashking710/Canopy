import asyncio
import json
import logging
import os

import aiomqtt

from canopy_master.audit_store import record_relayed_event
from canopy_master.db import SessionLocal
from canopy_master.store import store
from canopy_master.ws_manager import ws_manager

logger = logging.getLogger("canopy_master.mqtt")

MQTT_HOST = os.environ.get("CANOPY_MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("CANOPY_MQTT_PORT", "1883"))
RECONNECT_DELAY_SECONDS = 5

STATE_TOPIC_FILTER = "canopy/+/+/state"
# Every device at every site publishes its own audit-relay events to
# canopy/{site_id}/audit-events (see edge-agent's services/audit_relay.py) — a
# wildcard here is what turns "one site's devices reconcile with each other" into
# "master durably sees everything, across every site it's ever heard from."
AUDIT_TOPIC_FILTER = "canopy/+/audit-events"

# Unset means no auth/TLS, matching every edge-agent site's own default — see
# edge-agent's canopy_agent/services/mqtt_publisher.py (this is a separate package, so
# it keeps its own copy rather than importing across the two deployments) and
# docs/mqtt-security.md.
MQTT_USERNAME = os.environ.get("CANOPY_MQTT_USERNAME")
MQTT_PASSWORD = os.environ.get("CANOPY_MQTT_PASSWORD")
MQTT_TLS = os.environ.get("CANOPY_MQTT_TLS", "false").lower() in ("1", "true", "yes")
MQTT_CA_CERT = os.environ.get("CANOPY_MQTT_CA_CERT")


def _mqtt_connect_kwargs() -> dict:
    kwargs: dict = {}
    if MQTT_USERNAME:
        kwargs["username"] = MQTT_USERNAME
        kwargs["password"] = MQTT_PASSWORD
    if MQTT_TLS:
        kwargs["tls_params"] = aiomqtt.TLSParameters(ca_certs=MQTT_CA_CERT)
    return kwargs


async def subscribe_forever() -> None:
    while True:
        try:
            async with aiomqtt.Client(
                hostname=MQTT_HOST, port=MQTT_PORT, identifier="canopy-master", **_mqtt_connect_kwargs()
            ) as client:
                await client.subscribe(STATE_TOPIC_FILTER)
                await client.subscribe(AUDIT_TOPIC_FILTER, qos=1)
                logger.info(
                    "subscribed to %s and %s on %s:%s", STATE_TOPIC_FILTER, AUDIT_TOPIC_FILTER, MQTT_HOST, MQTT_PORT
                )
                async for message in client.messages:
                    topic_parts = str(message.topic).split("/")
                    if len(topic_parts) == 4 and topic_parts[-1] == "state":
                        await _handle_state_message(message, topic_parts)
                    elif len(topic_parts) == 3 and topic_parts[-1] == "audit-events":
                        _handle_audit_message(message, topic_parts)
                    else:
                        logger.warning("ignoring message on unrecognized topic shape %s", message.topic)
        except Exception:
            logger.warning(
                "mqtt connection lost or unavailable; retrying in %ss", RECONNECT_DELAY_SECONDS, exc_info=True
            )
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)


async def _handle_state_message(message: aiomqtt.Message, topic_parts: list[str]) -> None:
    try:
        _prefix, site_id, room_id, _suffix = topic_parts
        payload = json.loads(message.payload)
    except Exception:
        logger.warning("ignoring malformed message on topic %s", message.topic)
        return

    store.upsert_room(site_id, room_id, payload)
    await ws_manager.broadcast({"type": "room_update", "site_id": site_id, "room": payload})


def _handle_audit_message(message: aiomqtt.Message, topic_parts: list[str]) -> None:
    try:
        _prefix, site_id, _suffix = topic_parts
        payload = json.loads(message.payload)
    except Exception:
        logger.warning("ignoring malformed audit-relay message on topic %s", message.topic)
        return

    db = SessionLocal()
    try:
        record_relayed_event(db, site_id, payload)
    except Exception:
        logger.exception("failed to persist relayed audit event: %s", payload)
        db.rollback()
    finally:
        db.close()
