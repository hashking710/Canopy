import json
import logging

import pytest

from canopy_agent.logging_config import _JsonFormatter, _resolve_level, configure_logging


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """configure_logging() mutates the process-global root logger (level +
    handlers) — necessarily, since that's the whole point of it. Without this,
    a test in this file would leak its level/handler choice into every other
    test file in the same pytest run (including clobbering pytest's own
    caplog-capturing handler), since the root logger is shared process-wide."""
    root = logging.getLogger()
    original_level = root.level
    original_handlers = list(root.handlers)
    yield
    root.setLevel(original_level)
    root.handlers = original_handlers


def test_resolve_level_defaults_to_info(monkeypatch):
    monkeypatch.delenv("CANOPY_LOG_LEVEL", raising=False)
    assert _resolve_level() == logging.INFO


def test_resolve_level_reads_env_var(monkeypatch):
    monkeypatch.setenv("CANOPY_LOG_LEVEL", "DEBUG")
    assert _resolve_level() == logging.DEBUG


def test_resolve_level_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("CANOPY_LOG_LEVEL", "warning")
    assert _resolve_level() == logging.WARNING


def test_resolve_level_falls_back_to_info_on_garbage(monkeypatch):
    monkeypatch.setenv("CANOPY_LOG_LEVEL", "not-a-real-level")
    assert _resolve_level() == logging.INFO


def test_json_formatter_produces_valid_json_with_expected_fields():
    record = logging.LogRecord(
        name="canopy_agent.test", level=logging.WARNING, pathname=__file__, lineno=1,
        msg="something happened: %s", args=("detail",), exc_info=None,
    )
    formatted = _JsonFormatter().format(record)
    parsed = json.loads(formatted)
    assert parsed["level"] == "WARNING"
    assert parsed["logger"] == "canopy_agent.test"
    assert parsed["message"] == "something happened: detail"
    assert "timestamp" in parsed
    assert "exception" not in parsed


def test_json_formatter_includes_exception_info():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        record = logging.LogRecord(
            name="canopy_agent.test", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="failed", args=(), exc_info=sys.exc_info(),
        )
    parsed = json.loads(_JsonFormatter().format(record))
    assert "ValueError: boom" in parsed["exception"]


def test_configure_logging_sets_the_requested_level(monkeypatch):
    monkeypatch.setenv("CANOPY_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("CANOPY_LOG_FORMAT", "text")
    configure_logging("test-service")
    assert logging.getLogger().level == logging.ERROR


def test_configure_logging_uses_json_formatter_when_requested(monkeypatch):
    monkeypatch.setenv("CANOPY_LOG_FORMAT", "json")
    monkeypatch.delenv("CANOPY_LOG_LEVEL", raising=False)
    configure_logging("test-service")
    handler = logging.getLogger().handlers[0]
    assert isinstance(handler.formatter, _JsonFormatter)


def test_configure_logging_does_not_duplicate_handlers_on_repeat_calls(monkeypatch):
    monkeypatch.delenv("CANOPY_LOG_FORMAT", raising=False)
    configure_logging("test-service")
    configure_logging("test-service")
    assert len(logging.getLogger().handlers) == 1
