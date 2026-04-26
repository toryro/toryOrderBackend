"""Add closing_hour to stores and original_price to order_items

Revision ID: e5f6a7b8c9d0
Revises: b1c2d3e4f5a6
Create Date: 2026-04-26

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stores', sa.Column('closing_hour', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('order_items', sa.Column('original_price', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('stores', 'closing_hour')
    op.drop_column('order_items', 'original_price')
