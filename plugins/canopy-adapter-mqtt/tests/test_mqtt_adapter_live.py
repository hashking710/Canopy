"""
Real end-to-end test — publishes to an actual running MQTT broker (the one docker-
compose.yml already brings up on localhost:1883) and confirms the adapter's background
subscriber picks it up and read() returns it. Skipped automatically if no broker is
reachable, matching edge-agent's own test_audit_relay_two_devices_live.py.
"""

import asyncio
import socket
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import aiomqtt
import pytest
from canopy_adapter_mqtt import MqttSubscribeAdapter
from canopy_agent.models import Room

BROKER_HOST = "localhost"
BROKER_PORT = 1883


def _broker_reachable() -> bool:
    try:
        with socket.create_connection((BROKER_HOST, BROKER_PORT), timeout=1):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not _broker_reachable(), reason=f"no MQTT broker reachable at {BROKER_HOST}:{BROKER_PORT}")


def make_room(**adapter_config) -> Room:
    return Room(
        id="mqtt-live-room", room_type="greenhouse", path="~/mqtt-live-room",
        adapter_type="mqtt", metric_config={}, adapter_config=adapter_config,
    )


async def _wait_until_subscribed(adapter: MqttSubscribeAdapter, room: Room) -> None:
    # A non-retained MQTT message is only delivered to subscribers already subscribed
    # at publish time — publishing before the adapter's background subscriber has
    # actually connected and subscribed would just be lost. read() triggers
    # ensure_subscribed as a side effect (raising, since there's no message yet); once
    # the broker's own subscription set contains our topic, it's safe to publish.
    subscriber = adapter._get_subscriber(room.adapter_config["host"], room.adapter_config["port"])
    for _ in range(50):
        try:
            await adapter.read(room)
        except RuntimeError:
            pass
        if set(room.adapter_config["topics"].values()) <= subscriber._subscribed_topics:
            return
        await asyncio.sleep(0.1)
    pytest.fail("adapter never finished subscribing in time")


async def test_read_returns_a_genuinely_published_value():
    topic = "canopy-adapter-mqtt-test/temp"
    adapter = MqttSubscribeAdapter()
    room = make_room(host=BROKER_HOST, port=BROKER_PORT, topics={"temp_f": topic})
    await _wait_until_subscribed(adapter, room)

    async with aiomqtt.Client(hostname=BROKER_HOST, port=BROKER_PORT) as publisher:
        await publisher.publish(topic, payload=b"78.3", qos=0)

    for _ in range(50):
        try:
            values = await adapter.read(room)
            assert values == {"temp_f": 78.3}
            return
        except RuntimeError:
            await asyncio.sleep(0.1)
    pytest.fail("never received the published value in time")


async def test_two_rooms_on_the_same_broker_share_one_subscriber():
    topic_a = "canopy-adapter-mqtt-test/room-a/temp"
    topic_b = "canopy-adapter-mqtt-test/room-b/temp"
    adapter = MqttSubscribeAdapter()
    room_a = make_room(host=BROKER_HOST, port=BROKER_PORT, topics={"temp_f": topic_a})
    room_b = make_room(host=BROKER_HOST, port=BROKER_PORT, topics={"temp_f": topic_b})
    await _wait_until_subscribed(adapter, room_a)
    await _wait_until_subscribed(adapter, room_b)

    async with aiomqtt.Client(hostname=BROKER_HOST, port=BROKER_PORT) as publisher:
        await publisher.publish(topic_a, payload=b"70.0", qos=0)
        await publisher.publish(topic_b, payload=b"75.0", qos=0)

    async def read_until_ready(room, expected):
        for _ in range(50):
            try:
                values = await adapter.read(room)
                assert values == expected
                return
            except RuntimeError:
                await asyncio.sleep(0.1)
        pytest.fail("never received the published value in time")

    await read_until_ready(room_a, {"temp_f": 70.0})
    await read_until_ready(room_b, {"temp_f": 75.0})

    # Same (host, port) -> one shared subscriber, not one per room.
    assert len(adapter._subscribers) == 1
