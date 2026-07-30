"""add facility compliance state

Revision ID: 1dbaf5f7de42
Revises: f0f24904d241
Create Date: 2026-07-28 08:54:48.008642

Autogenerate also proposed adding a foreign key on packages.source_package_id ->
packages.id, same pre-existing model/schema drift noted in f0f24904d241 — left out
here too, for the same reason: not something to bundle silently into an unrelated
migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1dbaf5f7de42'
down_revision: Union[str, Sequence[str], None] = 'f0f24904d241'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('facility_compliance_state',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('state_code', sa.String(), nullable=False),
    sa.Column('updated_by', sa.String(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('facility_compliance_state')
