from datetime import date, datetime
from typing import Any

from canopy_agent.db import Base


def model_to_dict(obj: Base) -> dict[str, Any]:
    """Generic SQLAlchemy row -> JSON-able dict, so compliance list endpoints don't
    each need a hand-written response schema for what's fundamentally a table dump."""
    out: dict[str, Any] = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        out[column.name] = value
    return out
