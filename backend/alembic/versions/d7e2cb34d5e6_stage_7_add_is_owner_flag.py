"""stage 7: add is_owner flag for user roles

Revision ID: d7e2cb34d5e6
Revises: c6f1ba23c4d5
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7e2cb34d5e6'
down_revision: Union[str, Sequence[str], None] = 'c6f1ba23c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_owner boolean flag to users table
    # Default False; bootstrap logic in create_user service sets first user to True
    op.add_column(
        'users',
        sa.Column('is_owner', sa.Boolean, nullable=False, server_default='0')
    )


def downgrade() -> None:
    op.drop_column('users', 'is_owner')
