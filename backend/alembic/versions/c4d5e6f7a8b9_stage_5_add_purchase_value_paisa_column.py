"""stage 5: add purchase_value_paisa column to stock_movements

Revision ID: c4d5e6f7a8b9
Revises: b3d5e7f9a1c3
Create Date: 2026-08-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3d5e7f9a1c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add purchase_value_paisa column (nullable, NULL = not applicable for SALE/WASTAGE/CANCELLATION)
    op.add_column('stock_movements', sa.Column('purchase_value_paisa', sa.Integer(), nullable=True))


def downgrade() -> None:
    # Drop the purchase_value_paisa column
    op.drop_column('stock_movements', 'purchase_value_paisa')
