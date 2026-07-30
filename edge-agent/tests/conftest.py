import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from canopy_agent import models  # noqa: F401  # registers the `rooms` table compliance FKs reference
from canopy_agent.db import Base
from canopy_agent.deps import get_db
from canopy_agent.routers import alerts, backup as backup_router, compliance, facility, license as license_router, operators, rooms


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
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def operator_id(client):
    """A registered operator, for tests exercising compliance endpoints that now
    require a real operator_id instead of a free-text actor string."""
    return client.post("/api/operators", json={"name": "Test Operator"}).json()["id"]


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
