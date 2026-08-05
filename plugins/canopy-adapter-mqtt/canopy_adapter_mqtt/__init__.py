import asyncio
import logging
import os
import time
from typing import ClassVar

import aiomqtt
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

logger = logging.getLogger("canopy_adapter_mqtt")

RECONNECT_DELAY_SECONDS = 5
# A cached value this old is worse than no value at all — the device behind that
# topic has probably stopped publishing, and silently reporting a stale reading as
# current would be actively misleading, not just incomplete.
STALE_AFTER_SECONDS = 60


class MqttSubscribeAdapter(SensorAdapter):
    """
    Subscribes to arbitrary MQTT topics and maps them to metrics — the one adapter
    that makes every ESPHome, Tasmota, and Zigbee2MQTT device (in practice, most of
    the Home Assistant sensor ecosystem) usable as a Canopy sensor source with zero
    vendor-specific integration code, as long as it publishes a bare numeric payload
    to MQTT, which the vast majority of that ecosystem does by default.

    room.adapter_config shape:
        {
          "host": "192.168.1.20",   # optional — defaults to CANOPY_MQTT_HOST if unset
          "port": 1883,              # optional — default 1883
          "topics": {
            "temp_f": "esphome/greenhouse-a/temperature/state",
            "rh_pct": "esphome/greenhouse-a/humidity/state"
          }
        }

    MQTT is push-based (a device publishes when it has something to say); this
    adapter's read() is pull-based (the poller calls it every 5s). So read() itself
    never does network I/O — it returns whatever a shared background subscriber (one
    per broker, reused across every room pointed at that broker) has most recently
    cached for that room's configured topics. A topic that's never received a message,
    or hasn't recently enough (see STALE_AFTER_SECONDS), is treated as a real failure
    rather than silently reporting nothing or a stale value — matching every other
    adapter's "raise on failure, don't return partial/garbage data" contract.
    """

    plugin_name = "MQTT (generic subscribe)"
    plugin_description = (
        "Subscribes to arbitrary MQTT topics and maps them to metrics — works with "
        "any device publishing numeric values to MQTT (ESPHome, Tasmota, "
        "Zigbee2MQTT, Home Assistant, etc.), no vendor-specific integration needed."
    )
    category: ClassVar[str] = "local"
    config_schema: ClassVar[dict[str, str]] = {
        "host": "Broker hostname/IP (defaults to CANOPY_MQTT_HOST if unset)",
        "port": "Broker port, default 1883",
        "topics": "{metric_key: mqtt_topic} — one topic per metric this room reports",
    }

    def __init__(self) -> None:
        self._subscribers: dict[tuple[str, int], "_BrokerSubscriber"] = {}

    async def connect(self, room: Room) -> None:
        pass  # subscriber tasks start lazily on first read(), see _get_subscriber

    async def disconnect(self, room: Room) -> None:
        pass  # subscribers are shared across rooms/brokers; never torn down per-room
        # today — same as every other adapter (see adapters/registry.py's get_adapter)

    async def read(self, room: Room) -> dict[str, float]:
        config = room.adapter_config
        topics: dict[str, str] = config.get("topics") or {}
        if not topics:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.topics configured")

        host = config.get("host") or os.environ.get("CANOPY_MQTT_HOST")
        if not host:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.host and CANOPY_MQTT_HOST is unset")
        port = int(config.get("port", 1883))

        subscriber = self._get_subscriber(host, port)
        subscriber.ensure_subscribed(topics.values())

        now = time.monotonic()
        values: dict[str, float] = {}
        for metric, topic in topics.items():
            entry = subscriber.latest.get(topic)
            if entry is None:
                raise RuntimeError(f"metric '{metric}': no message ever received on topic '{topic}'")
            value, received_at = entry
            age = now - received_at
            if age > STALE_AFTER_SECONDS:
                raise RuntimeError(
                    f"metric '{metric}': last message on '{topic}' was {age:.0f}s ago "
                    f"(stale after {STALE_AFTER_SECONDS}s)"
                )
            values[metric] = value
        return values

    def _get_subscriber(self, host: str, port: int) -> "_BrokerSubscriber":
        key = (host, port)
        if key not in self._subscribers:
            self._subscribers[key] = _BrokerSubscriber(host, port)
        return self._subscribers[key]


def parse_numeric_payload(payload: bytes | str) -> float:
    """Split out from message handling so it's directly unit-testable without a real
    MQTT round-trip. Not every MQTT payload is a bare number — some devices publish
    JSON objects or human text — those are rejected, not guessed at."""
    return float(payload)


class _BrokerSubscriber:
    """One shared background subscriber per broker — N rooms pointed at the same
    broker share one MQTT connection instead of opening N, and share one growing
    subscription set as new topics get requested by newly-configured rooms."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self.latest: dict[str, tuple[float, float]] = {}  # topic -> (value, received_at monotonic)
        self._subscribed_topics: set[str] = set()
        self._pending_topics: set[str] = set()
        self._task: asyncio.Task | None = None

    def ensure_subscribed(self, topics) -> None:
        new = set(topics) - self._subscribed_topics - self._pending_topics
        if new:
            self._pending_topics |= new
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_forever())

    async def _run_forever(self) -> None:
        while True:
            try:
                async with aiomqtt.Client(hostname=self._host, port=self._port) as client:
                    await self._flush_pending_subscriptions(client)
                    logger.info(
                        "mqtt adapter subscribed to %d topic(s) on %s:%s",
                        len(self._subscribed_topics), self._host, self._port,
                    )

                    # A room configured after this loop started adds a topic to
                    # _pending_topics mid-flight. Waiting on `async for message in
                    # client.messages` alone would only notice it between incoming
                    # messages — on a quiet broker with no other traffic, a
                    # newly-added topic could then wait indefinitely to actually get
                    # subscribed. Polling with a timeout instead means the pending
                    # set gets flushed at least once a second regardless of traffic.
                    message_iter = client.messages.__aiter__()
                    while True:
                        try:
                            message = await asyncio.wait_for(message_iter.__anext__(), timeout=1.0)
                        except asyncio.TimeoutError:
                            pass
                        else:
                            self._handle_message(str(message.topic), message.payload)

                        if self._pending_topics:
                            await self._flush_pending_subscriptions(client)
            except Exception:
                logger.warning(
                    "mqtt adapter subscriber for %s:%s lost connection; retrying in %ss",
                    self._host, self._port, RECONNECT_DELAY_SECONDS, exc_info=True,
                )
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)

    async def _flush_pending_subscriptions(self, client: aiomqtt.Client) -> None:
        to_subscribe = self._subscribed_topics | self._pending_topics
        for topic in to_subscribe:
            await client.subscribe(topic, qos=0)
        self._subscribed_topics |= self._pending_topics
        self._pending_topics.clear()

    def _handle_message(self, topic: str, payload) -> None:
        try:
            value = parse_numeric_payload(payload)
        except (TypeError, ValueError):
            logger.debug("mqtt adapter: ignoring non-numeric payload on %s: %r", topic, payload)
            return
        self.latest[topic] = (value, time.monotonic())
