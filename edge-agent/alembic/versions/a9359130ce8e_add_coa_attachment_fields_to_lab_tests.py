"""add coa attachment fields to lab_tests

Revision ID: a9359130ce8e
Revises: 1dbaf5f7de42
Create Date: 2026-07-29 08:51:03.029684

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9359130ce8e'
down_revision: Union[str, Sequence[str], None] = '1dbaf5f7de42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('lab_tests', sa.Column('coa_filename', sa.String(), nullable=True))
    op.add_column('lab_tests', sa.Column('coa_stored_path', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('lab_tests', 'coa_stored_path')
    op.drop_column('lab_tests', 'coa_filename')
