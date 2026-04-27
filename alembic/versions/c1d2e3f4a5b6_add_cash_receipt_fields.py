"""add cash receipt fields to orders

Revision ID: c1d2e3f4a5b6
Revises: c2d3e4f5a6b7, e5f6a7b8c9d0
Create Date: 2026-04-27 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'c1d2e3f4a5b6'
down_revision = ('c2d3e4f5a6b7', 'e5f6a7b8c9d0')
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('orders', sa.Column('cash_receipt_status', sa.String(), nullable=True, server_default='NONE'))
    op.add_column('orders', sa.Column('cash_receipt_number', sa.String(), nullable=True))
    op.add_column('orders', sa.Column('cash_receipt_type', sa.String(), nullable=True))
    op.add_column('orders', sa.Column('cash_receipt_merchant_uid', sa.String(), nullable=True))


def downgrade():
    op.drop_column('orders', 'cash_receipt_merchant_uid')
    op.drop_column('orders', 'cash_receipt_type')
    op.drop_column('orders', 'cash_receipt_number')
    op.drop_column('orders', 'cash_receipt_status')
