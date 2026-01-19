"""Add archive_metadata_path to documents.

Revision ID: 20260118_archive_path
Revises: 20260118_rendered_html
Create Date: 2026-01-18 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260118_archive_path'
down_revision = '20260118_rendered_html'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'documents',
        sa.Column(
            'archive_metadata_path',
            sa.String(500),
            nullable=True,
            comment='Path to JSON archive with snapshot of staff/approver/settings data'
        )
    )


def downgrade():
    op.drop_column('documents', 'archive_metadata_path')
