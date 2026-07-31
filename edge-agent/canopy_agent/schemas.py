from pydantic import BaseModel


class MetricOut(BaseModel):
    key: str
    label: str
    unit: str
    value: float
    decimals: int


class RoomOut(BaseModel):
    id: str
    room_type: str
    path: str
    subtitle: str
    title: str
    badge: str
    footnote: str
    section: str | None
    tag_count: int
    stats: list[MetricOut]
    last_poll_at: str | None = None
    last_poll_error: str | None = None


class ReadingPoint(BaseModel):
    ts: str
    value: float


class RoomAdapterOut(BaseModel):
    id: int
    adapter_type: str
    adapter_config: dict


class RoomConfigOut(BaseModel):
    """The editable configuration behind a room — deliberately separate from RoomOut
    (which powers the room list/live-update payload broadcast over MQTT to every
    subscriber) so this only goes out when something specifically asks to edit a
    room, not on every poll."""

    adapter_type: str
    metric_config: dict
    adapter_config: dict
    extra_adapters: list[RoomAdapterOut] = []
