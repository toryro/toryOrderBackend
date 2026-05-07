"""merge_all_heads

Revision ID: 30e5cbdc444e
Revises: a9b8c7d6e5f4, c7b4ed1c49da
Create Date: 2026-05-08 00:58:34.978280

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30e5cbdc444e'
down_revision: Union[str, Sequence[str], None] = ('a9b8c7d6e5f4', 'c7b4ed1c49da')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
