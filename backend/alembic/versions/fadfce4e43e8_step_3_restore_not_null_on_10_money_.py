"""Step 3: Restore NOT NULL on 10 money columns

Revision ID: fadfce4e43e8
Revises: 300727b377ca
Create Date: 2026-08-15 13:34:41.510386

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fadfce4e43e8'
down_revision: Union[str, Sequence[str], None] = '300727b377ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Restore NOT NULL constraints on 10 money columns.

    These were lost in Migration B due to alter_column() not preserving nullable.
    Verified: all 10 columns have zero NULLs in data.
    stock_movements.purchase_price stays nullable (was originally nullable=True).
    """
    # === PRODUCTS: Restore NOT NULL on price, purchase_price ===
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.alter_column('price', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('purchase_price', existing_type=sa.Integer(), nullable=False)

    # === ORDERS: Restore NOT NULL on all 6 columns ===
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('subtotal', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('discount', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('tax', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('total', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('amount_received', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('change_amount', existing_type=sa.Integer(), nullable=False)

    # === ORDER_ITEMS: Restore NOT NULL on price, line_total ===
    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.alter_column('price', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('line_total', existing_type=sa.Integer(), nullable=False)

    # === STOCK_MOVEMENTS: Keep purchase_price nullable (as originally) ===
    # No change needed — leave nullable=True


def downgrade() -> None:
    """Downgrade is not possible — migration cannot be rolled back safely.

    NOT NULL constraints cannot be reliably removed in SQLite via batch_alter_table.
    Restore from backup: pos_pre_alembic_stamp.db
    """
    raise NotImplementedError(
        "Irreversible migration: NOT NULL constraints cannot be safely removed. "
        "Restore from backup: pos_pre_alembic_stamp.db"
    )
