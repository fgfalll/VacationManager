"""remove_unique_constraint_annual_schedule

Revision ID: f7cdd509ca73
Revises: 20260117_1200_extension_dates
Create Date: 2026-01-17 22:40:21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7cdd509ca73'
down_revision: Union[str, None] = '20260117_1200_extension_dates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite doesn't support dropping constraints directly, use batch mode
    with op.batch_alter_table('annual_schedule') as batch_op:
        batch_op.drop_constraint('uq_year_staff', type_='unique')


def downgrade() -> None:
    with op.batch_alter_table('annual_schedule') as batch_op:
        batch_op.create_unique_constraint('uq_year_staff', ['year', 'staff_id'])
