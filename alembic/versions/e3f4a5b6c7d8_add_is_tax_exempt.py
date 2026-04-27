"""add is_tax_exempt to menus and order_items

Revision ID: e3f4a5b6c7d8
Revises: c1d2e3f4a5b6
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa

revision = 'e3f4a5b6c7d8'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('menus', sa.Column('is_tax_exempt', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('order_items', sa.Column('is_tax_exempt', sa.Boolean(), nullable=True, server_default='false'))


def downgrade():
    op.drop_column('menus', 'is_tax_exempt')
    op.drop_column('order_items', 'is_tax_exempt')
