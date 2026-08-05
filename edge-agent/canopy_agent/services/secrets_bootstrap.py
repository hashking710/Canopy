import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.models import FacilitySecret


def load_secrets_into_environ(db: Session) -> None:
    """Runs once at startup (see main.py's lifespan), before the poller or any
    adapter is constructed — replays every credential set via the dashboard
    (routers/secrets.py) back into os.environ, so a container restart doesn't lose
    a credential someone configured through the UI instead of docker-compose.yml.
    Overwrites whatever docker-compose.yml/.env already set for the same key: once
    someone's explicitly set a value through the dashboard, that's the one that
    should win."""
    for row in db.execute(select(FacilitySecret)).scalars().all():
        os.environ[row.key] = row.value
