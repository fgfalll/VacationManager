"""add telegram link requests and permissions

Revision ID: f7a3b8c4d2e1
Revises: c8f2e9a5d6b1
Create Date: 2026-01-27 12:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7a3b8c4d2e1'
down_revision: Union[str, None] = '20260122_telegram'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    # Create telegram_link_requests table
    op.create_table(
        'telegram_link_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('telegram_user_id', sa.String(50), nullable=False, index=True),
        sa.Column('telegram_username', sa.String(100), nullable=True),
        sa.Column('phone_number', sa.String(50), nullable=True),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=True),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='linkrequeststatus'), 
                  nullable=False, default='pending', index=True),
        sa.Column('staff_id', sa.Integer(), sa.ForeignKey('staff.id'), nullable=True),
        sa.Column('approved_by', sa.String(200), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    
    # Add telegram_permissions column to staff table
    op.add_column('staff', sa.Column('telegram_permissions', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove telegram_permissions column from staff table
    op.drop_column('staff', 'telegram_permissions')
    
    # Drop telegram_link_requests table
    op.drop_table('telegram_link_requests')
    
    # Drop enum type
    op.execute('DROP TYPE IF EXISTS linkrequeststatus')
