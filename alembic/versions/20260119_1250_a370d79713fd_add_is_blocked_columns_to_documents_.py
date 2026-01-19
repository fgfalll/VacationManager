"""add is_blocked columns to documents table

Revision ID: a370d79713fd
Revises: afe78f2fa26e
Create Date: 2026-01-19 12:50:42
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a370d79713fd'
down_revision: Union[str, None] = 'afe78f2fa26e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_blocked columns for documents table
    op.add_column('documents', sa.Column('is_blocked', sa.Boolean(), server_default='0', nullable=False, comment='Чи заблоковано редагування документа'))
    op.add_column('documents', sa.Column('blocked_reason', sa.String(length=500), nullable=True, comment='Причина блокування документа'))

    # Set is_blocked for existing documents where scan exists or status is processed
    op.execute("UPDATE documents SET is_blocked = 1 WHERE file_scan_path IS NOT NULL OR status = 'processed'")

    op.create_index(op.f('ix_documents_is_blocked'), 'documents', ['is_blocked'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_documents_is_blocked'), table_name='documents')
    op.drop_column('documents', 'blocked_reason')
    op.drop_column('documents', 'is_blocked')
