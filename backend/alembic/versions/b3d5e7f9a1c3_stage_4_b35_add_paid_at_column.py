"""stage 4 b35: add paid_at column for tracking payment timestamp

Revision ID: b3d5e7f9a1c3
Revises: ad8ba306eabb
Create Date: 2026-08-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3d5e7f9a1c3'
down_revision: Union[str, Sequence[str], None] = 'ad8ba306eabb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add paid_at column (nullable, NULL = not yet paid)
    op.add_column('orders', sa.Column('paid_at', sa.DateTime(), nullable=True))

    # Backfill: existing PAID orders were created and paid in the same operation.
    # Set their paid_at = created_at. Do NOT backfill OPEN or CANCELLED orders.
    op.execute(sa.text("UPDATE orders SET paid_at = created_at WHERE status = 'PAID'"))


def downgrade() -> None:
    # Drop the paid_at column
    op.drop_column('orders', 'paid_at')
