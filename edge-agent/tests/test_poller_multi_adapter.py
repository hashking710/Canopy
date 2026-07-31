from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from canopy_agent.db import Base
from canopy_agent.models import Reading, Room, RoomAdapter
from canopy_agent.services import poller


class StaticAdapter:
    """Stands in for a real adapter, reporting whatever fixed values were
    configured on the room/extra-adapter's own adapter_config — the pure-software
    equivalent of "a BLE controller for temp/RH plus a separate CO2 probe"."""

    async def connect(self, room):
        pass

    async def read(self, room):
        return dict(room.adapter_config.get("values", {}))

    async def disconnect(self, room):
        pass


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    return TestSessionLocal


async def test_poll_once_merges_primary_and_extra_adapter_readings(monkeypatch):
    TestSessionLocal = make_session()
    monkeypatch.setattr(poller, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr(poller, "get_adapter", lambda room: StaticAdapter())

    session = TestSessionLocal()
    session.add(
        Room(
            id="multi-room", room_type="greenhouse", path="~/multi-room",
            adapter_type="primary_sensor", adapter_config={"values": {"temp_f": 78.0, "rh_pct": 55.0}},
            metric_config={
                "temp_f": {"label": "temp", "unit": "F", "decimals": 1},
                "rh_pct": {"label": "RH", "unit": "%", "decimals": 1},
                "co2_ppm": {"label": "CO2", "unit": "ppm", "decimals": 0},
            },
        )
    )
    session.add(
        RoomAdapter(
            room_id="multi-room", adapter_type="co2_probe", adapter_config={"values": {"co2_ppm": 810.0}},
        )
    )
    session.commit()
    session.close()

    await poller.poll_once()

    session = TestSessionLocal()
    readings = {r.metric: r.value for r in session.execute(select(Reading)).scalars().all()}
    assert readings == {"temp_f": 78.0, "rh_pct": 55.0, "co2_ppm": 810.0}


async def test_poll_once_extra_adapter_wins_on_key_collision(monkeypatch):
    """Documented, deliberate behavior: a later adapter's key overwrites an
    earlier one's — config order is meaningful, not arbitrary."""
    TestSessionLocal = make_session()
    monkeypatch.setattr(poller, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr(poller, "get_adapter", lambda room: StaticAdapter())

    session = TestSessionLocal()
    session.add(
        Room(
            id="collide-room", room_type="greenhouse", path="~/collide-room",
            adapter_type="primary_sensor", adapter_config={"values": {"temp_f": 70.0}},
            metric_config={"temp_f": {"label": "temp", "unit": "F", "decimals": 1}},
        )
    )
    session.add(
        RoomAdapter(
            room_id="collide-room", adapter_type="secondary_sensor", adapter_config={"values": {"temp_f": 99.0}},
        )
    )
    session.commit()
    session.close()

    await poller.poll_once()

    session = TestSessionLocal()
    reading = session.execute(select(Reading)).scalars().one()
    assert reading.value == 99.0


async def test_poll_once_room_with_no_extra_adapters_is_unaffected(monkeypatch):
    """The overwhelmingly common single-adapter case needs no changes at all."""
    TestSessionLocal = make_session()
    monkeypatch.setattr(poller, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr(poller, "get_adapter", lambda room: StaticAdapter())

    session = TestSessionLocal()
    session.add(
        Room(
            id="plain-room", room_type="greenhouse", path="~/plain-room",
            adapter_type="primary_sensor", adapter_config={"values": {"temp_f": 72.0}},
            metric_config={"temp_f": {"label": "temp", "unit": "F", "decimals": 1}},
        )
    )
    session.commit()
    session.close()

    await poller.poll_once()

    session = TestSessionLocal()
    reading = session.execute(select(Reading)).scalars().one()
    assert reading.value == 72.0
