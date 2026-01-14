"""add_pib_dav_to_staff

Revision ID: e0dbc3708841
Revises: 98f8fa1e71fb
Create Date: 2026-01-14 18:07:38
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0dbc3708841'
down_revision: Union[str, None] = '98f8fa1e71fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('staff', sa.Column('pib_dav', sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column('staff', 'pib_dav')
