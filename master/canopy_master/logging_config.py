import json
import logging
import os
import sys
from datetime import datetime, timezone

# Mirrors edge-agent's canopy_agent/logging_config.py exactly — kept as its own
# copy rather than a shared import, same reasoning as mqtt_subscriber.py's own
# note on why master keeps its own copy of things edge-agent also has: this is a
# separate deployment/package, not a shared library between the two.
#
# CANOPY_LOG_LEVEL: DEBUG/INFO/WARNING/ERROR/CRITICAL, default INFO.
# CANOPY_LOG_FORMAT: "text" (default) or "json" (one JSON object per line).

_LEVEL_NAMES = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _resolve_level() -> int:
    raw = os.environ.get("CANOPY_LOG_LEVEL", "INFO").upper()
    if raw not in _LEVEL_NAMES:
        raw = "INFO"
    return getattr(logging, raw)


def configure_logging(service_name: str) -> None:
    level = _resolve_level()
    fmt = os.environ.get("CANOPY_LOG_FORMAT", "text").lower()

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                f"%(asctime)s [{service_name}] %(levelname)-8s %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = True
