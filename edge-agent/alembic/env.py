from logging.config import fileConfig

from alembic import context

# Import every module that defines tables so Base.metadata is fully populated for
# autogenerate — SQLAlchemy only knows about a table once its module has been imported.
from canopy_agent import compliance_models, models  # noqa: F401
from canopy_agent.db import Base, engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection (`alembic upgrade head --sql`)."""
    context.configure(
        url=str(engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the same engine (and thus the same CANOPY_DATA_DIR-aware
    database file) the application itself uses — one source of truth for the DB URL."""
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
