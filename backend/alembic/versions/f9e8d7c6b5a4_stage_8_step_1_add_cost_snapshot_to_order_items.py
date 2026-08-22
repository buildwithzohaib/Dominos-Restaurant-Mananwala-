"""Stage 8 step 1: add cost snapshot to order_items

Revision ID: f9e8d7c6b5a4
Revises: e8f3dc45e6f7
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9e8d7c6b5a4'
down_revision: Union[str, Sequence[str], None] = 'e8f3dc45e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('order_items', sa.Column('cost', sa.Integer, nullable=True))


def downgrade() -> None:
    op.drop_column('order_items', 'cost')
