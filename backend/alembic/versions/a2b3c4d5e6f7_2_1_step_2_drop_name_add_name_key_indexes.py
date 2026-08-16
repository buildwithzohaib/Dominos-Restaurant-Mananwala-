"""2.1 Step 2: Drop name column, set NOT NULL, add unique name_key indexes

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'a2b3c4d5e6f7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Rebuild products and categories tables:
    - Drop name column (data preserved in name_raw)
    - Set name_raw/name_display/name_key to NOT NULL
    - Drop old indexes on name
    - Add UNIQUE indexes on name_key for dedup detection

    WARNING: This breaks the backend immediately. All code must be updated
    to use name_display and name_key before running the app.
    """
    connection = op.get_bind()

    # Check if ix_products_sku exists before table rebuild (it may be dropped by batch)
    sku_index_info = connection.execute(
        text("PRAGMA index_info(ix_products_sku)")
    ).fetchall()
    sku_index_exists_before = len(sku_index_info) > 0

    # ===== REBUILD PRODUCTS TABLE =====
    with op.batch_alter_table('products', schema=None) as batch_op:
        # Drop the old non-unique index on name
        batch_op.drop_index('ix_products_name')

        # Drop the old name column (data already in name_raw)
        batch_op.drop_column('name')

        # Set NOT NULL on the three normalization columns
        batch_op.alter_column('name_raw', existing_type=sa.String(255), nullable=False)
        batch_op.alter_column('name_display', existing_type=sa.String(255), nullable=False)
        batch_op.alter_column('name_key', existing_type=sa.String(255), nullable=False)

        # Create UNIQUE index on name_key for dedup detection
        batch_op.create_index('ix_products_name_key', ['name_key'], unique=True)

    # Verify and recreate ix_products_sku if it was dropped by batch rebuild
    # (batch_alter_table with SQLite can silently drop indexes)
    if sku_index_exists_before:
        current_indexes = connection.execute(
            text("PRAGMA index_list(products)")
        ).fetchall()

        sku_exists_now = any(idx[1] == 'ix_products_sku' for idx in current_indexes)

        if not sku_exists_now:
            # Recreate the unique index on sku
            connection.execute(
                text("CREATE UNIQUE INDEX ix_products_sku ON products(sku)")
            )

    # ===== REBUILD CATEGORIES TABLE =====
    with op.batch_alter_table('categories', schema=None) as batch_op:
        # Drop the old unique index on name (was enforcing uniqueness)
        batch_op.drop_index('ix_categories_name')

        # Drop the old name column (data already in name_raw)
        batch_op.drop_column('name')

        # Set NOT NULL on the three normalization columns
        batch_op.alter_column('name_raw', existing_type=sa.String(255), nullable=False)
        batch_op.alter_column('name_display', existing_type=sa.String(255), nullable=False)
        batch_op.alter_column('name_key', existing_type=sa.String(255), nullable=False)

        # Create UNIQUE index on name_key for dedup detection
        batch_op.create_index('ix_categories_name_key', ['name_key'], unique=True)


def downgrade() -> None:
    """Downgrade is not possible: the name column data is gone after rebuild.
    Restore from backup instead."""
    raise NotImplementedError(
        "Cannot downgrade: name column was dropped and data is unrecoverable. "
        "Restore from pos_before_2.1_migration2.db instead."
    )
