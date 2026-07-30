import asyncio
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from canopy_agent.db import Base
from canopy_agent.models import Room
from canopy_agent.services import poller


class SlowAdapter:
    """Stands in for a real adapter doing real I/O (a cloud API call, a serial
    read) that takes real wall-clock time — used to prove rooms are polled
    concurrently, not one at a time."""

    async def connect(self, room):
        pass

    async def read(self, room):
        await asyncio.sleep(0.2)
        return {"temp_f": 72.0}

    async def disconnect(self, room):
        pass


async def test_poll_once_reads_rooms_concurrently_not_sequentially(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(poller, "SessionLocal", TestSessionLocal)

    session = TestSessionLocal()
    room_count = 5
    for i in range(room_count):
        session.add(
            Room(
                id=f"room-{i}",
                room_type="greenhouse",
                path=f"~/room-{i}",
                adapter_type="slow",
                metric_config={"temp_f": {"label": "temp", "unit": "F", "decimals": 1}},
            )
        )
    session.commit()
    session.close()

    monkeypatch.setattr(poller, "get_adapter", lambda room: SlowAdapter())

    start = time.monotonic()
    await poller.poll_once()
    elapsed = time.monotonic() - start

    # Sequential would take ~room_count * 0.2s (1.0s for 5 rooms); concurrent stays
    # close to a single 0.2s read regardless of room count. 0.6s is a generous
    # ceiling that's still well below the sequential-case duration, so this fails
    # loudly if polling ever regresses back to one-room-at-a-time.
    assert elapsed < 0.6, f"poll_once took {elapsed:.2f}s for {room_count} rooms — looks sequential, not concurrent"
