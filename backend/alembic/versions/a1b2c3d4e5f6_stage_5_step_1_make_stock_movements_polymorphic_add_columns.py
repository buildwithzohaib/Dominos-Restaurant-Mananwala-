"""Task 0.7 Step 1: Make stock_movements polymorphic (add item_type, item_id)

Revision ID: a1b2c3d4e5f6
Revises: fadfce4e43e8
Create Date: 2026-08-15 20:00:00.000000

This is Task 0.7 Step A: add item_type and item_id columns, backfill them,
make them NOT NULL, and create the new composite index. The old product_id
column and its FK are dropped in Step B.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'fadfce4e43e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Stage 5 Step A: Add polymorphic columns to stock_movements.

    1. Add item_type (nullable) — will hold 'PRODUCT' | 'INGREDIENT'
    2. Add item_id (nullable) — will hold the product or ingredient id
    3. Backfill: set item_type='PRODUCT', item_id=product_id for all 10 rows
    4. Alter both columns to NOT NULL
    5. Create composite index (item_type, item_id) for future ingredient queries

    Old product_id column and FK stay for now; dropped in Step B via batch_alter_table.
    """
    # === STEP 1: Add new columns (nullable) ===
    op.add_column('stock_movements', sa.Column('item_type', sa.String(20), nullable=True))
    op.add_column('stock_movements', sa.Column('item_id', sa.Integer(), nullable=True))

    # === STEP 2: Backfill existing rows ===
    # All 10 current rows have product_id set; copy to the new columns.
    op.execute("UPDATE stock_movements SET item_type='PRODUCT', item_id=product_id")

    # === STEP 3: Alter to NOT NULL (safe: backfill confirmed no NULLs) ===
    with op.batch_alter_table('stock_movements', schema=None) as batch_op:
        batch_op.alter_column('item_type', existing_type=sa.String(20), nullable=False)
        batch_op.alter_column('item_id', existing_type=sa.Integer(), nullable=False)

    # === STEP 4: Create new composite index ===
    # Used by Stage 5 for product queries and Stage 6 for ingredient queries.
    op.create_index(
        'ix_stock_movements_item_type_item_id',
        'stock_movements',
        ['item_type', 'item_id']
    )


def downgrade() -> None:
    """Downgrade: remove new columns and index."""
    op.drop_index('ix_stock_movements_item_type_item_id', table_name='stock_movements')
    with op.batch_alter_table('stock_movements', schema=None) as batch_op:
        batch_op.drop_column('item_type')
        batch_op.drop_column('item_id')
