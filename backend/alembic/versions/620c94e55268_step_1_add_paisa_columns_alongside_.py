"""Step 1: Add paisa columns alongside Numeric

Revision ID: 620c94e55268
Revises: 061dfeee0a0f
Create Date: 2026-08-15 13:16:37.321280

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '620c94e55268'
down_revision: Union[str, Sequence[str], None] = '061dfeee0a0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Step 1: Add paisa columns alongside existing Numeric columns."""
    # Products (2 columns)
    op.add_column('products', sa.Column('price_paisa', sa.Integer(), nullable=True))
    op.add_column('products', sa.Column('purchase_price_paisa', sa.Integer(), nullable=True))

    # Orders (6 columns)
    op.add_column('orders', sa.Column('subtotal_paisa', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('discount_paisa', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('tax_paisa', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('total_paisa', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('amount_received_paisa', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('change_amount_paisa', sa.Integer(), nullable=True))

    # OrderItems (2 columns)
    op.add_column('order_items', sa.Column('price_paisa', sa.Integer(), nullable=True))
    op.add_column('order_items', sa.Column('line_total_paisa', sa.Integer(), nullable=True))

    # StockMovements (1 column)
    op.add_column('stock_movements', sa.Column('purchase_price_paisa', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove paisa columns."""
    op.drop_column('stock_movements', 'purchase_price_paisa')
    op.drop_column('order_items', 'line_total_paisa')
    op.drop_column('order_items', 'price_paisa')
    op.drop_column('orders', 'change_amount_paisa')
    op.drop_column('orders', 'amount_received_paisa')
    op.drop_column('orders', 'total_paisa')
    op.drop_column('orders', 'tax_paisa')
    op.drop_column('orders', 'discount_paisa')
    op.drop_column('orders', 'subtotal_paisa')
    op.drop_column('products', 'purchase_price_paisa')
    op.drop_column('products', 'price_paisa')
