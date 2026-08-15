"""Step 2: Drop old Numeric columns, rename paisa to originals

Revision ID: 300727b377ca
Revises: 620c94e55268
Create Date: 2026-08-15 13:23:43.987512

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '300727b377ca'
down_revision: Union[str, Sequence[str], None] = '620c94e55268'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Step 2: Drop old Numeric columns, rename _paisa columns to originals.

    Order matters for SQLite batch_alter_table:
    1. Drop old columns first (in separate batch blocks)
    2. Then rename _paisa columns to original names (in separate batch blocks)
    Do not merge — SQLite table rebuild can see name collisions mid-process.
    """
    # === PRODUCTS: DROP old columns ===
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('price')
        batch_op.drop_column('purchase_price')

    # === PRODUCTS: RENAME _paisa columns ===
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.alter_column('price_paisa', new_column_name='price')
        batch_op.alter_column('purchase_price_paisa', new_column_name='purchase_price')

    # === ORDERS: DROP old columns ===
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_column('subtotal')
        batch_op.drop_column('discount')
        batch_op.drop_column('tax')
        batch_op.drop_column('total')
        batch_op.drop_column('amount_received')
        batch_op.drop_column('change_amount')

    # === ORDERS: RENAME _paisa columns ===
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('subtotal_paisa', new_column_name='subtotal')
        batch_op.alter_column('discount_paisa', new_column_name='discount')
        batch_op.alter_column('tax_paisa', new_column_name='tax')
        batch_op.alter_column('total_paisa', new_column_name='total')
        batch_op.alter_column('amount_received_paisa', new_column_name='amount_received')
        batch_op.alter_column('change_amount_paisa', new_column_name='change_amount')

    # === ORDER_ITEMS: DROP old columns ===
    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.drop_column('price')
        batch_op.drop_column('line_total')

    # === ORDER_ITEMS: RENAME _paisa columns ===
    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.alter_column('price_paisa', new_column_name='price')
        batch_op.alter_column('line_total_paisa', new_column_name='line_total')

    # === STOCK_MOVEMENTS: DROP old columns ===
    with op.batch_alter_table('stock_movements', schema=None) as batch_op:
        batch_op.drop_column('purchase_price')

    # === STOCK_MOVEMENTS: RENAME _paisa columns ===
    with op.batch_alter_table('stock_movements', schema=None) as batch_op:
        batch_op.alter_column('purchase_price_paisa', new_column_name='purchase_price')


def downgrade() -> None:
    """Downgrade is not possible — old Numeric columns were dropped.

    Restore from pos_pre_alembic_stamp.db or pos_before_money_migration.db
    """
    raise NotImplementedError(
        "Irreversible migration: old Numeric columns were dropped. "
        "Restore from backup: pos_pre_alembic_stamp.db"
    )
