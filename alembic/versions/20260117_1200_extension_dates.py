"""Add extension date fields to documents

Revision ID: 20260117_1200_extension_dates
Revises: 20260117_1100_document_correction
Create Date: 2026-01-17 12:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by alembic.
revision = '20260117_1200_extension_dates'
down_revision = '20260117_1100_document_correction'
branch_labels = None
depends_on = None


def upgrade():
    # Додаємо поля extension_start_date та old_contract_end_date
    op.add_column('documents', sa.Column('extension_start_date', sa.Date(), nullable=True, comment='Початок продовження контракту (для документів продовження)'))
    op.add_column('documents', sa.Column('old_contract_end_date', sa.Date(), nullable=True, comment='Дата закінчення попереднього контракту (для документів продовження)'))


def downgrade():
    op.drop_column('documents', 'old_contract_end_date')
    op.drop_column('documents', 'extension_start_date')
