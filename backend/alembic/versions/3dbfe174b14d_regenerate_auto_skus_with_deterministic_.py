"""regenerate_auto_skus_with_deterministic_format

Revision ID: 3dbfe174b14d
Revises: a2b3c4d5e6f7
Create Date: 2026-08-17 11:33:03.295516

Regenerate SKUs for products 5 and 6 (test products with AUTO-timestamp SKUs)
using the new deterministic SKU generation format (TASK 2.5).

Before:
  ID 5 (zinger): AUTO-1786607860.89804 -> FAS-ZIN-001
  ID 6 (ZZ Test Product Do Not Use): AUTO-1786871582.163785 -> FAS-ZZT-001

After migration, these SKUs follow the pattern {CAT_PREFIX}-{PROD_ABBR}-{SEQ}.
Seed SKUs (IDs 1-4) remain untouched:
  ID 1: FF-NUG-001 (unchanged)
  ID 2: FF-FRY-001 (unchanged)
  ID 3: DEAL-ZFD-001 (unchanged)
  ID 4: DRK-PEP-001 (unchanged)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3dbfe174b14d'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Regenerate SKUs for products 5 and 6 using deterministic format.

    Steps:
    1. Query all existing SKUs (except IDs 5 and 6)
    2. For each test product (5 and 6), compute new SKU using build_sku
    3. Update the products' SKUs in place
    """
    from app.services.sku_service import build_sku

    connection = op.get_bind()

    # Get all existing SKUs except for products 5 and 6
    result = connection.execute(sa.text("SELECT sku FROM products WHERE id NOT IN (5, 6)"))
    existing_skus = {row[0] for row in result}

    # Get product 5 details
    result = connection.execute(sa.text(
        "SELECT p.id, p.name_key, c.name_key, c.id FROM products p "
        "JOIN categories c ON p.category_id = c.id WHERE p.id = 5"
    ))
    row = result.fetchone()
    if row:
        prod_id, prod_name_key, cat_name_key, cat_id = row
        new_sku_5 = build_sku(cat_name_key, prod_name_key, cat_id, existing_skus)
        connection.execute(sa.text("UPDATE products SET sku = :sku WHERE id = 5"), {"sku": new_sku_5})
        existing_skus.add(new_sku_5)  # Add to taken set for next product

    # Get product 6 details
    result = connection.execute(sa.text(
        "SELECT p.id, p.name_key, c.name_key, c.id FROM products p "
        "JOIN categories c ON p.category_id = c.id WHERE p.id = 6"
    ))
    row = result.fetchone()
    if row:
        prod_id, prod_name_key, cat_name_key, cat_id = row
        new_sku_6 = build_sku(cat_name_key, prod_name_key, cat_id, existing_skus)
        connection.execute(sa.text("UPDATE products SET sku = :sku WHERE id = 6"), {"sku": new_sku_6})


def downgrade() -> None:
    """
    Restore original AUTO- SKUs for products 5 and 6.
    """
    connection = op.get_bind()

    # Restore original AUTO- SKUs
    connection.execute(sa.text(
        "UPDATE products SET sku = :sku WHERE id = 5"
    ), {"sku": "AUTO-1786607860.89804"})

    connection.execute(sa.text(
        "UPDATE products SET sku = :sku WHERE id = 6"
    ), {"sku": "AUTO-1786871582.163785"})
