"""Add correction tracking fields to documents.

Revision ID: 20260117_1100_document_correction
Revises: 20260117_1050_attendance_correction
Create Date: 2026-01-17 11:00

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '20260117_1100_document_correction'
down_revision = '20260117_1050_attendance_correction'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add correction tracking fields to documents table
    op.add_column('documents', sa.Column('is_correction', sa.Boolean(), nullable=False, default=False, server_default='0'))
    op.add_column('documents', sa.Column('correction_month', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('correction_year', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('correction_sequence', sa.Integer(), nullable=False, default=1, server_default='1'))

    # Create indexes for correction queries
    op.create_index(op.f('ix_documents_correction_month'), 'documents', ['correction_month'])
    op.create_index(op.f('ix_documents_correction_year'), 'documents', ['correction_year'])


def downgrade() -> None:
    op.drop_index(op.f('ix_documents_correction_year'), table_name='documents')
    op.drop_index(op.f('ix_documents_correction_month'), table_name='documents')
    op.drop_column('documents', 'correction_sequence')
    op.drop_column('documents', 'correction_year')
    op.drop_column('documents', 'correction_month')
    op.drop_column('documents', 'is_correction')
