"""add_tabel_approval

Revision ID: 12a3f4b5c6d7
Revises: e0dbc3708841
Create Date: 2026-01-15 22:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '12a3f4b5c6d7'
down_revision: Union[str, None] = 'e0dbc3708841'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tabel_approval',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('is_correction', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('correction_month', sa.Integer(), nullable=True),
        sa.Column('correction_year', sa.Integer(), nullable=True),
        sa.Column('is_approved', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('approved_by', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tabel_approval_correction_month'), 'tabel_approval', ['correction_month'], unique=False)
    op.create_index(op.f('ix_tabel_approval_correction_year'), 'tabel_approval', ['correction_year'], unique=False)
    op.create_index(op.f('ix_tabel_approval_is_approved'), 'tabel_approval', ['is_approved'], unique=False)
    op.create_index(op.f('ix_tabel_approval_month'), 'tabel_approval', ['month'], unique=False)
    op.create_index(op.f('ix_tabel_approval_year'), 'tabel_approval', ['year'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tabel_approval_year'), 'tabel_approval')
    op.drop_index(op.f('ix_tabel_approval_month'), 'tabel_approval')
    op.drop_index(op.f('ix_tabel_approval_is_approved'), 'tabel_approval')
    op.drop_index(op.f('ix_tabel_approval_correction_year'), 'tabel_approval')
    op.drop_index(op.f('ix_tabel_approval_correction_month'), 'tabel_approval')
    op.drop_table('tabel_approval')
