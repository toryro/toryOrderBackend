"""Add daily_closings table

Revision ID: a9b8c7d6e5f4
Revises: f6b4911cf7e4
Create Date: 2026-05-07 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, None] = 'f6b4911cf7e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'daily_closings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.Column('business_date', sa.String(), nullable=False),
        sa.Column('total_revenue', sa.Integer(), nullable=True, default=0),
        sa.Column('order_count', sa.Integer(), nullable=True, default=0),
        sa.Column('card_revenue', sa.Integer(), nullable=True, default=0),
        sa.Column('cash_revenue', sa.Integer(), nullable=True, default=0),
        sa.Column('deferred_revenue', sa.Integer(), nullable=True, default=0),
        sa.Column('cancelled_amount', sa.Integer(), nullable=True, default=0),
        sa.Column('cancelled_count', sa.Integer(), nullable=True, default=0),
        sa.Column('memo', sa.String(), nullable=True),
        sa.Column('closed_by_id', sa.Integer(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('snapshot_json', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id']),
        sa.ForeignKeyConstraint(['closed_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_daily_closings_id', 'daily_closings', ['id'])
    op.create_index('ix_daily_closings_store_id', 'daily_closings', ['store_id'])
    op.create_index('ix_daily_closings_business_date', 'daily_closings', ['business_date'])


def downgrade() -> None:
    op.drop_index('ix_daily_closings_business_date', table_name='daily_closings')
    op.drop_index('ix_daily_closings_store_id', table_name='daily_closings')
    op.drop_index('ix_daily_closings_id', table_name='daily_closings')
    op.drop_table('daily_closings')
