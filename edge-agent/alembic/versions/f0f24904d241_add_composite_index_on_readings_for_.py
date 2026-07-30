"""add composite index on readings for room+metric+ts queries

Revision ID: f0f24904d241
Revises: 6fcee4b85466
Create Date: 2026-07-27 18:24:08.422278

Autogenerate also proposed adding a foreign key on packages.source_package_id ->
packages.id, unrelated to this change and left out here deliberately — it's a
pre-existing model/schema drift (FKs aren't enforced under this project's SQLite
setup anyway, see models.py's Room docstring), not something to bundle silently
into an index-only migration.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f0f24904d241'
down_revision: Union[str, Sequence[str], None] = '6fcee4b85466'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('ix_readings_room_metric_ts', 'readings', ['room_id', 'metric', 'ts'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_readings_room_metric_ts', table_name='readings')
