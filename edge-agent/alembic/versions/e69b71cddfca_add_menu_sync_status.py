"""add menu sync status

Revision ID: e69b71cddfca
Revises: 25f2937dc1eb
Create Date: 2026-09-01 19:31:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e69b71cddfca'
down_revision: Union[str, Sequence[str], None] = '25f2937dc1eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('menu_sync_status',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('last_synced_at', sa.DateTime(), nullable=True),
    sa.Column('last_result', sa.JSON(), nullable=False),
    sa.Column('last_error', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('menu_sync_status')
