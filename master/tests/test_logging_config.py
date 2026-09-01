import json
import logging

import pytest

from canopy_master.logging_config import _JsonFormatter, _resolve_level, configure_logging


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """See edge-agent's test_logging_config.py for why this is needed —
    configure_logging() mutates the process-global root logger."""
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


def test_resolve_level_falls_back_to_info_on_garbage(monkeypatch):
    monkeypatch.setenv("CANOPY_LOG_LEVEL", "not-a-real-level")
    assert _resolve_level() == logging.INFO


def test_json_formatter_produces_valid_json_with_expected_fields():
    record = logging.LogRecord(
        name="canopy_master.test", level=logging.WARNING, pathname=__file__, lineno=1,
        msg="something happened: %s", args=("detail",), exc_info=None,
    )
    parsed = json.loads(_JsonFormatter().format(record))
    assert parsed["level"] == "WARNING"
    assert parsed["logger"] == "canopy_master.test"
    assert parsed["message"] == "something happened: detail"
    assert "timestamp" in parsed


def test_configure_logging_sets_the_requested_level(monkeypatch):
    monkeypatch.setenv("CANOPY_LOG_LEVEL", "ERROR")
    configure_logging("test-service")
    assert logging.getLogger().level == logging.ERROR


def test_configure_logging_does_not_duplicate_handlers_on_repeat_calls(monkeypatch):
    monkeypatch.delenv("CANOPY_LOG_FORMAT", raising=False)
    configure_logging("test-service")
    configure_logging("test-service")
    assert len(logging.getLogger().handlers) == 1
