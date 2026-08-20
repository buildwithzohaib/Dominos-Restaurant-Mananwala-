"""stage 7: expand pin column for bcrypt hash storage

Revision ID: c6f1ba23c4d5
Revises: d6f0ab23c4e5
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6f1ba23c4d5'
down_revision: Union[str, Sequence[str], None] = 'd6f0ab23c4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite does not enforce VARCHAR length constraints — all text columns have TEXT affinity.
    # A 60-character bcrypt hash stores fine in a column declared VARCHAR(10).
    # No schema change needed.
    pass


def downgrade() -> None:
    # SQLite does not enforce VARCHAR length constraints — no schema change needed.
    pass
