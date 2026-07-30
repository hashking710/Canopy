import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from canopy_master import models  # noqa: F401  # registers RelayedAuditEntry's table
from canopy_master.db import Base
from canopy_master.deps import get_db
from canopy_master.routers import audit


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


@pytest.fixture()
def client():
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
    app.include_router(audit.router)
    app.dependency_overrides[get_db] = override_get_db
    # Exposed so tests can seed data directly through the same in-memory DB the app
    # itself queries, without going through a second dependency-override generator.
    app.state.test_session_factory = TestSessionLocal

    with TestClient(app) as test_client:
        yield test_client
