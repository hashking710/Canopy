import json
import logging
import os
import sys
from datetime import datetime, timezone

# Before this existed, the whole app ran on whatever Python's/uvicorn's logging
# defaults happened to be — no level control, no structured output, and every one of
# the ~12 files that actually call logger.*() had no guaranteed destination. Not
# something you can run "in production" and trust: a dead adapter or a failed backup
# only shows up if someone happens to be tailing stdout at the right moment.
#
# CANOPY_LOG_LEVEL: DEBUG/INFO/WARNING/ERROR/CRITICAL, default INFO.
# CANOPY_LOG_FORMAT: "text" (default — readable on a Pi's local console/journalctl)
#   or "json" (one JSON object per line, for feeding a log aggregator).

_LEVEL_NAMES = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class _JsonFormatter(logging.Formatter):
    """Hand-rolled rather than a new dependency (python-json-logger/structlog) —
    the shape needed here is small and fixed: timestamp, level, logger name,
    message, and exception info when present."""

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
    """Call once, at the very top of the process (before any other module that
    might log gets imported) — see main.py. `service_name` is cosmetic, just
    distinguishes which process a line came from when multiple services' logs are
    aggregated together (edge-agent, master)."""
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
    # Replace rather than append — a second call (or a test re-importing this
    # module) shouldn't double every log line.
    root.handlers = [handler]

    # uvicorn installs its own handlers/formatters on these three loggers by
    # default; route them through the same handler instead so "the app's own
    # logs" and "uvicorn's request/error logs" are one consistent stream, not two
    # different formats interleaved.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = True
