"""add role to operators

Revision ID: 0c97aa8a51bd
Revises: 2d2a06d8844a
Create Date: 2026-09-01 12:08:16.246813

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c97aa8a51bd'
down_revision: Union[str, Sequence[str], None] = '2d2a06d8844a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing operators default to 'admin', not the model's own new-row default of
    # 'operator' — before this column existed, every registered operator could
    # already do everything the shared API token allowed; the role system is meant
    # to gate NEW operators down from that baseline, not retroactively strip
    # capability from whoever's already registered at a real facility.
    op.add_column('operators', sa.Column('role', sa.String(), nullable=False, server_default='admin'))
    # NOTE: autogenerate also detected a `packages.source_package_id` self-FK that
    # isn't part of this change — same pre-existing model/DB drift already flagged
    # and stripped from prior migrations in this file's history (see
    # 2d2a06d8844a, 58c9f5441db9); left for a dedicated migration, not bundled here.


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('operators', 'role')
