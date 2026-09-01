"""add operator notification prefs

Revision ID: fa5784bdf469
Revises: e69b71cddfca
Create Date: 2026-09-01 19:32:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa5784bdf469'
down_revision: Union[str, Sequence[str], None] = 'e69b71cddfca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # A new opt-in capability, not a new restriction (unlike role) — every existing
    # operator safely defaults to "off", nobody's capability changes.
    op.add_column('operators', sa.Column('notify_email', sa.String(), nullable=True))
    op.add_column('operators', sa.Column('notify_on_alerts', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('operators', sa.Column('notify_on_system_errors', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('operators', sa.Column('notify_min_severity', sa.String(), nullable=False, server_default='critical'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('operators', 'notify_min_severity')
    op.drop_column('operators', 'notify_on_system_errors')
    op.drop_column('operators', 'notify_on_alerts')
    op.drop_column('operators', 'notify_email')
