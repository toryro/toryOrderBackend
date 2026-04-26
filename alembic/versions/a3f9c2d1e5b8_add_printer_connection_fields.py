"""Add printer connection fields to Store

Revision ID: a3f9c2d1e5b8
Revises: 92611163620f
Create Date: 2026-04-24 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a3f9c2d1e5b8'
down_revision: Union[str, Sequence[str], None] = '92611163620f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stores', sa.Column('receipt_printer_type', sa.String(), nullable=True))
    op.add_column('stores', sa.Column('receipt_printer_host', sa.String(), nullable=True))
    op.add_column('stores', sa.Column('receipt_printer_port', sa.String(), nullable=True))
    op.add_column('stores', sa.Column('receipt_printer_baud', sa.Integer(), nullable=True))
    op.add_column('stores', sa.Column('kitchen_printer_type', sa.String(), nullable=True))
    op.add_column('stores', sa.Column('kitchen_printer_host', sa.String(), nullable=True))
    op.add_column('stores', sa.Column('kitchen_printer_port', sa.String(), nullable=True))
    op.add_column('stores', sa.Column('kitchen_printer_baud', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('stores', 'kitchen_printer_baud')
    op.drop_column('stores', 'kitchen_printer_port')
    op.drop_column('stores', 'kitchen_printer_host')
    op.drop_column('stores', 'kitchen_printer_type')
    op.drop_column('stores', 'receipt_printer_baud')
    op.drop_column('stores', 'receipt_printer_port')
    op.drop_column('stores', 'receipt_printer_host')
    op.drop_column('stores', 'receipt_printer_type')
