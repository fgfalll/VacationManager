"""Add email and phone fields to staff

Revision ID: 20260118_email_phone
Revises: 20260118_archive_path
Create Date: 2026-01-18 20:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by alembic
revision = '20260118_email_phone'
down_revision = '20260118_archive_path'
branch_labels = None
depends_on = None


def upgrade():
    # Add email and phone columns to staff table
    op.add_column('staff', sa.Column('email', sa.String(255), nullable=True))
    op.add_column('staff', sa.Column('phone', sa.String(50), nullable=True))


def downgrade():
    op.drop_column('staff', 'phone')
    op.drop_column('staff', 'email')
