"""add_correction_sequence

Revision ID: a1b2c3d4e5f6
Revises: 12a3f4b5c6d7
Create Date: 2026-01-16 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '12a3f4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add correction_sequence column for tracking multiple corrections per month
    op.add_column('tabel_approval', sa.Column('correction_sequence', sa.Integer(), nullable=False, server_default='1'))
    op.create_index(op.f('ix_tabel_approval_correction_sequence'), 'tabel_approval', ['correction_sequence'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tabel_approval_correction_sequence'), 'tabel_approval')
    op.drop_column('tabel_approval', 'correction_sequence')
