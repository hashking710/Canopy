import pytest
from canopy_adapter_mqtt import MqttSubscribeAdapter, parse_numeric_payload
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="mqtt-room", room_type="greenhouse", path="~/mqtt-room",
        adapter_type="mqtt", metric_config={}, adapter_config=adapter_config,
    )


# ---- pure payload parsing — no network involved -----------------------------------


def test_parse_numeric_payload_from_bytes():
    assert parse_numeric_payload(b"72.5") == 72.5


def test_parse_numeric_payload_from_str():
    assert parse_numeric_payload("72.5") == 72.5


def test_parse_numeric_payload_rejects_json():
    with pytest.raises(ValueError):
        parse_numeric_payload(b'{"value": 72.5}')


def test_parse_numeric_payload_rejects_text():
    with pytest.raises(ValueError):
        parse_numeric_payload(b"ON")


# ---- config validation — no network involved ---------------------------------------


async def test_read_without_topics_raises():
    adapter = MqttSubscribeAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.topics"):
        await adapter.read(make_room())


async def test_read_without_host_or_env_raises(monkeypatch):
    monkeypatch.delenv("CANOPY_MQTT_HOST", raising=False)
    adapter = MqttSubscribeAdapter()
    with pytest.raises(RuntimeError, match="CANOPY_MQTT_HOST"):
        await adapter.read(make_room(topics={"temp_f": "some/topic"}))


def test_plugin_metadata_is_set():
    assert MqttSubscribeAdapter.plugin_name == "MQTT (generic subscribe)"
    assert "topics" in MqttSubscribeAdapter.config_schema
