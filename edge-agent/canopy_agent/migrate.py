from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # edge-agent/
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


def upgrade_to_head() -> None:
    """Bring the database's schema up to the latest migration. Run at startup instead
    of Base.metadata.create_all — every schema change (new table, new column) is a
    tracked migration from here on, so a real deployment's data survives an upgrade
    instead of the schema drifting silently or needing the DB wiped."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    command.upgrade(config, "head")
