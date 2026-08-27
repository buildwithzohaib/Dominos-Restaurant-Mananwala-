"""Phase 11: add product_type column to support deal products

Revision ID: 12c4d5e6f7a1
Revises: 11b3c4d5e6f7
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '12c4d5e6f7a1'
down_revision: Union[str, Sequence[str], None] = '11b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add product_type column with default 'PRODUCT' so all existing rows remain unchanged
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('product_type', sa.String(length=20), nullable=False, server_default='PRODUCT'))


def downgrade() -> None:
    # Remove product_type column
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('product_type')
