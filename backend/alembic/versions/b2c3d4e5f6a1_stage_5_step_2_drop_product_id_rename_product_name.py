"""Task 0.7 Step 2: Drop product_id, rename product_name -> item_name

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-08-15 20:10:00.000000

This is Task 0.7 Step B: drop the old product_id column and its FK constraint,
rename product_name to item_name (because it's now a snapshot of either product
or ingredient name), and drop the old index. The new (item_type, item_id) index
is deterministically dropped and recreated to ensure consistent schema state
regardless of whether the batch_alter_table rebuild preserves or drops it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a1'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Stage 5 Step B: Rebuild table, drop old column, rename snapshot field.

    Uses batch_alter_table which rebuilds the table in SQLite. All operations
    inside the batch block are atomic: they succeed together or fail together.

    Operations inside batch_alter_table:
    1. Drop index ix_stock_movements_product_id (old product_id index)
    2. Drop column product_id (and its FK constraint)
    3. Rename product_name -> item_name (snapshot is now item-agnostic)

    Operations after batch (deterministic index handling):
    4. Drop (item_type, item_id) index if it exists (batch may or may not preserve it)
    5. Recreate (item_type, item_id) index unconditionally

    This ensures the schema is deterministic regardless of SQLite's index handling.
    """
    with op.batch_alter_table('stock_movements', schema=None) as batch_op:
        batch_op.drop_index('ix_stock_movements_product_id')
        batch_op.drop_column('product_id')
        batch_op.alter_column('product_name', new_column_name='item_name')

    # === DETERMINISTIC INDEX HANDLING ===
    # Drop the new index if it exists (batch_alter_table may or may not preserve it),
    # then recreate it unconditionally. This ensures consistent schema state.
    try:
        op.drop_index('ix_stock_movements_item_type_item_id', table_name='stock_movements')
    except Exception:
        # Index doesn't exist; that's fine. Continue.
        pass

    # Unconditionally recreate the index.
    op.create_index(
        'ix_stock_movements_item_type_item_id',
        'stock_movements',
        ['item_type', 'item_id']
    )


def downgrade() -> None:
    """Downgrade: restore product_id column, rename item_name back, restore old index.

    This is best-effort only. Restoring the FK constraint is not possible
    without access to the original schema. Restore from backup if needed.
    """
    with op.batch_alter_table('stock_movements', schema=None) as batch_op:
        batch_op.alter_column('item_name', new_column_name='product_name')
        batch_op.add_column('product_id', sa.Integer(), nullable=True)

    # Restore old index (on product_id)
    op.create_index(
        'ix_stock_movements_product_id',
        'stock_movements',
        ['product_id']
    )
