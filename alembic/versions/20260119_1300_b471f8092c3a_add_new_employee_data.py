"""Add new_employee_data column to documents

Revision ID: b471f8092c3a
Revises: a370d79713fd
Create Date: 2026-01-19 13:00

"""
from typing import Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b471f8092c3a'
down_revision: Union[str, None] = 'a370d79713fd'
branch_labels: Union[str, list[str], None] = None
depends_on: Union[str, list[str], None] = None


def upgrade() -> None:
    # Use JSON type (SQLite-compatible) for storing new employee data
    op.add_column(
        'documents',
        sa.Column('new_employee_data', sa.JSON(), nullable=True, comment='Дані нового співробітника для документів прийому на роботу')
    )


def downgrade() -> None:
    # Remove the new_employee_data column
    op.drop_column('documents', 'new_employee_data')
