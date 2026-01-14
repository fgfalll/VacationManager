"""add_deletion_notes_to_attendance

Revision ID: 98f8fa1e71fb
Revises:
Create Date: 2026-01-14 17:44:54
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98f8fa1e71fb'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('attendance', sa.Column('deletion_notes', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('attendance', 'deletion_notes')
