"""Add store_payment_configs table

Revision ID: d5e6f7a8b9c0
Revises: 30e5cbdc444e
Create Date: 2026-05-11 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = '30e5cbdc444e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'store_payment_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.Column('portone_store_id', sa.String(), nullable=False),
        sa.Column('portone_api_secret', sa.String(), nullable=False),
        sa.Column('channel_key', sa.String(), nullable=False),
        sa.Column('pg_provider', sa.String(), nullable=True, server_default='tosspayments'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id'),
    )
    op.create_index('ix_store_payment_configs_id', 'store_payment_configs', ['id'])
    op.create_index('ix_store_payment_configs_store_id', 'store_payment_configs', ['store_id'])


def downgrade() -> None:
    op.drop_index('ix_store_payment_configs_store_id', table_name='store_payment_configs')
    op.drop_index('ix_store_payment_configs_id', table_name='store_payment_configs')
    op.drop_table('store_payment_configs')
