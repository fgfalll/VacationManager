"""Add Telegram fields to staff

Revision ID: 20260122_telegram
Revises: d2bf0d856ef5
Create Date: 2026-01-22 12:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260122_telegram'
down_revision: Union[str, None] = 'd2bf0d856ef5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add telegram_user_id and telegram_username columns to staff table
    op.add_column('staff', sa.Column('telegram_user_id', sa.String(50), nullable=True, comment='Telegram user ID for Mini App authentication'))
    op.add_column('staff', sa.Column('telegram_username', sa.String(100), nullable=True, comment='Telegram username (without @)'))
    op.create_index(op.f('ix_staff_telegram_user_id'), 'staff', ['telegram_user_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_staff_telegram_user_id'), table_name='staff')
    op.drop_column('staff', 'telegram_username')
    op.drop_column('staff', 'telegram_user_id')
