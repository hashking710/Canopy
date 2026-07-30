import pytest
from fastapi import HTTPException

from canopy_master import auth


def test_passthrough_when_token_unset(monkeypatch):
    monkeypatch.setattr(auth, "MASTER_TOKEN", None)
    auth.require_token(authorization=None)  # must not raise
    assert auth.is_valid_token(None) is True


def test_rejects_missing_header_when_token_set(monkeypatch):
    monkeypatch.setattr(auth, "MASTER_TOKEN", "secret")
    with pytest.raises(HTTPException) as exc:
        auth.require_token(authorization=None)
    assert exc.value.status_code == 401


def test_accepts_correct_bearer_token(monkeypatch):
    monkeypatch.setattr(auth, "MASTER_TOKEN", "secret")
    auth.require_token(authorization="Bearer secret")  # must not raise
