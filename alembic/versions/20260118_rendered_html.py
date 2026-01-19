"""Add rendered_html column to documents table.

Revision ID: 20260118_rendered_html
Revises: f7cdd509ca73
Create Date: 2026-01-18

"""
from typing import Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '20260118_rendered_html'
down_revision = 'f7cdd509ca73'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add rendered_html column
    op.add_column('documents', sa.Column('rendered_html', sa.Text(), nullable=True, comment='Rendered HTML content for document preview'))


def downgrade() -> None:
    op.drop_column('documents', 'rendered_html')
