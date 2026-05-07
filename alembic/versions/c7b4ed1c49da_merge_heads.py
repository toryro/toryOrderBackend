"""merge_heads

Revision ID: c7b4ed1c49da
Revises: b2c3d4e5f6a7, e3f4a5b6c7d8
Create Date: 2026-05-06 13:53:55.173683

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7b4ed1c49da'
down_revision: Union[str, Sequence[str], None] = ('b2c3d4e5f6a7', 'e3f4a5b6c7d8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
