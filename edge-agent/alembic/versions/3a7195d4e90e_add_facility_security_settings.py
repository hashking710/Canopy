"""add facility security settings

Revision ID: 3a7195d4e90e
Revises: a9359130ce8e
Create Date: 2026-07-29 18:39:17.976352

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a7195d4e90e'
down_revision: Union[str, Sequence[str], None] = 'a9359130ce8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('facility_security_settings',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('require_operator_pins', sa.Boolean(), nullable=False),
    sa.Column('updated_by', sa.String(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('facility_security_settings')
