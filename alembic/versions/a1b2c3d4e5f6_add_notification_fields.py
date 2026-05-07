"""Add notification fields to store, brand, order

Revision ID: a1b2c3d4e5f6
Revises: f6b4911cf7e4
Create Date: 2026-04-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f6b4911cf7e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Brand: 브랜드 공용 알림 채널
    op.add_column('brands', sa.Column('kakao_profile_key', sa.String(), nullable=True))
    op.add_column('brands', sa.Column('sms_sender_number', sa.String(), nullable=True))

    # Store: 매장별 알림 설정
    op.add_column('stores', sa.Column('notification_type', sa.String(), nullable=True, server_default='PLATFORM'))
    op.add_column('stores', sa.Column('kakao_profile_key', sa.String(), nullable=True))
    op.add_column('stores', sa.Column('sms_sender_number', sa.String(), nullable=True))

    # Order: 포장 알림 수신 전화번호
    op.add_column('orders', sa.Column('customer_phone', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'customer_phone')
    op.drop_column('stores', 'sms_sender_number')
    op.drop_column('stores', 'kakao_profile_key')
    op.drop_column('stores', 'notification_type')
    op.drop_column('brands', 'sms_sender_number')
    op.drop_column('brands', 'kakao_profile_key')
