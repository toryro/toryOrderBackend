"""Add table_type to tables

Revision ID: b1c2d3e4f5a6
Revises: 0f0dd46deb52
Create Date: 2026-04-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'a3f9c2d1e5b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tables', sa.Column('table_type', sa.String(), nullable=True, server_default='DINE_IN'))


def downgrade() -> None:
    op.drop_column('tables', 'table_type')
