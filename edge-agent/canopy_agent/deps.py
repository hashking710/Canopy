from collections.abc import Iterator

from sqlalchemy.orm import Session

from canopy_agent.db import SessionLocal


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
