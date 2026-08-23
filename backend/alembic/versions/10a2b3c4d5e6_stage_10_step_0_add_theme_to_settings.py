"""Stage 10 step 0: add theme to settings

Revision ID: 10a2b3c4d5e6
Revises: f9e8d7c6b5a4
Create Date: 2026-08-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'f9e8d7c6b5a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('settings', sa.Column('theme', sa.String(30),
                  nullable=False, server_default='amber'))


def downgrade() -> None:
    op.drop_column('settings', 'theme')
