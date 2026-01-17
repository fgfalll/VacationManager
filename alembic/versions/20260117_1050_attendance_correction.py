"""add_attendance_correction_fields

Add correction tracking fields to attendance table.

Revision ID: 20260117_1050
Revises: a1b2c3d4e5f6
Create Date: 2026-01-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260117_1050_attendance_correction'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Add correction tracking fields to attendance table
    op.add_column('attendance', sa.Column('is_correction', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('attendance', sa.Column('correction_month', sa.Integer(), nullable=True))
    op.add_column('attendance', sa.Column('correction_year', sa.Integer(), nullable=True))
    op.add_column('attendance', sa.Column('correction_sequence', sa.Integer(), nullable=False, server_default='1'))
    
    # Create indexes for faster queries
    op.create_index(op.f('ix_attendance_is_correction'), 'attendance', ['is_correction'], unique=False)
    op.create_index(op.f('ix_attendance_correction_month'), 'attendance', ['correction_month'], unique=False)
    op.create_index(op.f('ix_attendance_correction_year'), 'attendance', ['correction_year'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_attendance_correction_year'), 'attendance')
    op.drop_index(op.f('ix_attendance_correction_month'), 'attendance')
    op.drop_index(op.f('ix_attendance_is_correction'), 'attendance')
    op.drop_column('attendance', 'correction_sequence')
    op.drop_column('attendance', 'correction_year')
    op.drop_column('attendance', 'correction_month')
    op.drop_column('attendance', 'is_correction')
