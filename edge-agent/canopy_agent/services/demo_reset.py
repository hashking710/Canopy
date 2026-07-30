import asyncio
import logging

from sqlalchemy.orm import Session

from canopy_agent.db import Base, SessionLocal
from canopy_agent.seed import seed
from canopy_agent.seed_compliance import seed_compliance
from canopy_agent.services.coa_storage import COA_DIR

logger = logging.getLogger("canopy_agent.demo_reset")

# Only used when CANOPY_DEMO_MODE is on — a public demo instance needs to stay
# genuinely interactive (that's the actual sell) rather than read-only, so instead
# of blocking mutation, any visitor tampering just gets wiped on a fixed interval.
DEMO_RESET_INTERVAL_SECONDS = 3600


def _clear_coa_uploads() -> None:
    """Wiping the lab_tests table (below) drops every coa_stored_path reference, but
    that alone leaves the actual uploaded files sitting on disk with nothing pointing
    at them anymore — on a public, ever-resetting demo instance, that's an unbounded
    disk leak (a visitor can upload a file every hour, forever). Since demo mode's
    whole model is "everything gets wiped back to the fixed baseline," the files get
    the same treatment as every table: gone, not selectively reconciled."""
    if not COA_DIR.exists():
        return
    for path in COA_DIR.iterdir():
        if path.is_file():
            path.unlink()


def reset_demo_data(db: Session) -> None:
    """Wipes every table, then reseeds the same fixed demo dataset every other
    'try it out' path in this project already uses (seed.py/seed_compliance.py).
    Deletes in reverse dependency order so foreign keys are respected."""
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    _clear_coa_uploads()
    seed(db)
    seed_compliance(db)


async def demo_reset_forever() -> None:
    while True:
        await asyncio.sleep(DEMO_RESET_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            reset_demo_data(db)
            logger.info("demo data reset")
        except Exception:
            logger.exception("demo data reset failed")
        finally:
            db.close()
