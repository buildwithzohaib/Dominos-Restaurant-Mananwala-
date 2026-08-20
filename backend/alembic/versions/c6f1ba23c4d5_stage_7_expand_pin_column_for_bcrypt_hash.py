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
    # Expand pin column from String(10) to String(100) to accommodate bcrypt hashes (~60 chars)
    op.alter_column(
        'users',
        'pin',
        type_=sa.String(100),
        existing_type=sa.String(10),
        existing_nullable=False
    )


def downgrade() -> None:
    # Shrink back to String(10) — will fail if any hashes are > 10 chars
    op.alter_column(
        'users',
        'pin',
        type_=sa.String(10),
        existing_type=sa.String(100),
        existing_nullable=False
    )
