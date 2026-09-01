"""add strains and genetics links

Revision ID: 25f2937dc1eb
Revises: 0c97aa8a51bd
Create Date: 2026-09-01 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '25f2937dc1eb'
down_revision: Union[str, Sequence[str], None] = '0c97aa8a51bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('strains',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('lineage', sa.String(), nullable=False),
    sa.Column('strain_type', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=False),
    sa.Column('thc_pct_typical', sa.Float(), nullable=True),
    sa.Column('cbd_pct_typical', sa.Float(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    # Nullable, additive links to the new registry — existing free-text `strain`
    # columns on these three tables are untouched, no backfill. Same "no
    # op.create_foreign_key" reasoning as 6fcee4b85466: SQLite can't add a real FK
    # constraint without a full batch-mode table rebuild, and this project already
    # relies on the ORM relationship, not DB-level enforcement, for this.
    op.add_column('plant_batches', sa.Column('strain_id', sa.String(), nullable=True))
    op.add_column('plants', sa.Column('strain_id', sa.String(), nullable=True))
    op.add_column('harvests', sa.Column('strain_id', sa.String(), nullable=True))
    # What a package is listed for sale at — optional, for menu sync
    # (services/menu_data.py) to push a price if the facility wants to supply one.
    op.add_column('packages', sa.Column('list_price_cents', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('packages', 'list_price_cents')
    op.drop_column('harvests', 'strain_id')
    op.drop_column('plants', 'strain_id')
    op.drop_column('plant_batches', 'strain_id')
    op.drop_table('strains')
