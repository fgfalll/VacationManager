"""add stale tracking fields to documents

Revision ID: c8f2e9a5d6b1
Revises: b471f8092c3a
Create Date: 2026-01-20 22:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8f2e9a5d6b1'
down_revision: Union[str, None] = 'b471f8092c3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add stale tracking fields
    op.add_column('documents', sa.Column(
        'status_changed_at', 
        sa.DateTime(), 
        nullable=True,
        comment='Timestamp of last status change'
    ))
    op.add_column('documents', sa.Column(
        'stale_notification_count', 
        sa.Integer(), 
        server_default='0',
        nullable=False,
        comment='Number of stale notifications sent'
    ))
    op.add_column('documents', sa.Column(
        'stale_explanation', 
        sa.Text(), 
        nullable=True,
        comment='User explanation for why document is taking long'
    ))
    
    # Set status_changed_at to updated_at for existing records
    op.execute("UPDATE documents SET status_changed_at = updated_at WHERE status_changed_at IS NULL")


def downgrade() -> None:
    op.drop_column('documents', 'stale_explanation')
    op.drop_column('documents', 'stale_notification_count')
    op.drop_column('documents', 'status_changed_at')
