import os
import tempfile

# Must run before any canopy_agent module is imported — canopy_agent.db reads
# CANOPY_DATA_DIR (and binds a real, module-level SQLAlchemy engine to
# <data dir>/canopy.db) at *import* time, not per-call. Most of this test suite
# never touches that real engine at all (client/db_session fixtures below build
# their own isolated in-memory SQLite engine instead) — but a few code paths
# (e.g. services/personal_notify.py's default `db=None` behavior, exercised via
# services/error_reporting.py's report_system_error() in test_error_reporting.py)
# open a session via canopy_agent.db.SessionLocal() directly. Without this, those
# tests would silently read from — and pytest runs would depend on the contents
# of — whatever real, on-disk edge-agent/data/canopy.db a developer happens to
# have from actually running the app locally.
os.environ["CANOPY_DATA_DIR"] = tempfile.mkdtemp(prefix="canopy-test-data-")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from canopy_agent import models  # noqa: F401  # registers the `rooms` table compliance FKs reference
from canopy_agent.db import Base
from canopy_agent.deps import get_db
from canopy_agent.routers import alerts, backup as backup_router, compliance, facility, health as health_router, license as license_router, menu_sync as menu_sync_router, operators, rooms, secrets as secrets_router, strains as strains_router


@pytest.fixture()
def client():
    # StaticPool: TestClient dispatches sync route/dependency calls to a worker thread,
    # and sqlite's default per-thread pooling would otherwise hand that thread a
    # separate, empty :memory: database from the one `create_all` just populated.
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(facility.router)
    app.include_router(rooms.router)
    app.include_router(compliance.router)
    app.include_router(operators.router)
    app.include_router(alerts.router)
    app.include_router(license_router.router)
    app.include_router(backup_router.router)
    app.include_router(secrets_router.router)
    app.include_router(health_router.router)
    app.include_router(strains_router.router)
    app.include_router(menu_sync_router.router)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def operator_id(client):
    """A registered operator, for tests exercising compliance endpoints that now
    require a real operator_id instead of a free-text actor string."""
    return client.post("/api/operators", json={"name": "Test Operator"}).json()["id"]


@pytest.fixture(autouse=True)
def _reset_task_health():
    """services/health.py's _task_health is a process-global dict — same
    cross-test leakage risk as the notification-channel cache below, and the
    same fix: reset it before and after every test."""
    import canopy_agent.services.health as health

    health._task_health = {}
    yield
    health._task_health = {}


@pytest.fixture(autouse=True)
def _reset_notification_channel_cache():
    """notifications/registry.py caches one instance per channel for the whole
    process lifetime (same reasoning as adapters/registry.py) — without resetting
    it, a test that exercises get_active_channels() under one env var
    configuration would leak stale channel instances into whatever test runs
    next in the same pytest session."""
    import canopy_agent.notifications.registry as registry

    registry._instances = None
    yield
    registry._instances = None


@pytest.fixture(autouse=True)
def _reset_menu_sync_registry():
    """menu_sync/registry.py caches a single MenuSync instance for the whole
    process lifetime (same reasoning as compliance_sync/registry.py) — reset it
    so a test that sets CANOPY_MENU_SYNC doesn't leak a stale instance/factory
    map into whatever test runs next."""
    import canopy_agent.menu_sync.registry as registry

    registry._instance = None
    registry._factories = None
    yield
    registry._instance = None
    registry._factories = None


@pytest.fixture()
def db_session():
    """A plain SQLAlchemy session against a fresh in-memory DB, for tests that call
    service-layer functions directly rather than going through the HTTP layer."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
