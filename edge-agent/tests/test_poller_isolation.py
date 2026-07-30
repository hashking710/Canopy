from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from canopy_agent.adapters.mock import MockAdapter
from canopy_agent.db import Base
from canopy_agent.models import Reading, Room
from canopy_agent.services import poller


class FailingAdapter:
    """Stands in for a real adapter (network/hardware) that's down or misconfigured."""

    async def connect(self, room):
        pass

    async def read(self, room):
        raise RuntimeError("simulated adapter failure")

    async def disconnect(self, room):
        pass


async def test_poll_once_isolates_a_failing_room_from_the_rest(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(poller, "SessionLocal", TestSessionLocal)

    session = TestSessionLocal()
    session.add(
        Room(
            id="good-room",
            room_type="greenhouse",
            path="~/good-room",
            adapter_type="mock",
            metric_config={"temp_f": {"label": "temp", "unit": "F", "decimals": 1, "min": 70, "max": 80}},
        )
    )
    session.add(Room(id="bad-room", room_type="greenhouse", path="~/bad-room", adapter_type="broken", metric_config={}))
    session.commit()
    session.close()

    def fake_get_adapter(room: Room):
        return FailingAdapter() if room.adapter_type == "broken" else MockAdapter()

    monkeypatch.setattr(poller, "get_adapter", fake_get_adapter)

    await poller.poll_once()

    session = TestSessionLocal()
    readings = session.execute(select(Reading)).scalars().all()
    assert [r.room_id for r in readings] == ["good-room"]


async def test_poll_once_records_health_for_both_success_and_failure(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(poller, "SessionLocal", TestSessionLocal)

    session = TestSessionLocal()
    session.add(
        Room(
            id="good-room",
            room_type="greenhouse",
            path="~/good-room",
            adapter_type="mock",
            metric_config={"temp_f": {"label": "temp", "unit": "F", "decimals": 1, "min": 70, "max": 80}},
        )
    )
    session.add(Room(id="bad-room", room_type="greenhouse", path="~/bad-room", adapter_type="broken", metric_config={}))
    session.commit()
    session.close()

    def fake_get_adapter(room: Room):
        return FailingAdapter() if room.adapter_type == "broken" else MockAdapter()

    monkeypatch.setattr(poller, "get_adapter", fake_get_adapter)

    await poller.poll_once()

    session = TestSessionLocal()
    good_room = session.get(Room, "good-room")
    bad_room = session.get(Room, "bad-room")

    assert good_room.last_poll_at is not None
    assert good_room.last_poll_error is None

    assert bad_room.last_poll_at is not None
    assert "simulated adapter failure" in bad_room.last_poll_error
