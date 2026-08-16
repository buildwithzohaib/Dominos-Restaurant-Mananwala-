"""2.1 Step 1: Add text normalization columns to products and categories

Revision ID: f1a2b3c4d5e6
Revises: e70842f37507
Create Date: 2026-08-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'e70842f37507'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add three new nullable columns to products
    op.add_column('products', sa.Column('name_raw', sa.String(255), nullable=True))
    op.add_column('products', sa.Column('name_display', sa.String(255), nullable=True))
    op.add_column('products', sa.Column('name_key', sa.String(255), nullable=True))

    # Add three new nullable columns to categories
    op.add_column('categories', sa.Column('name_raw', sa.String(255), nullable=True))
    op.add_column('categories', sa.Column('name_display', sa.String(255), nullable=True))
    op.add_column('categories', sa.Column('name_key', sa.String(255), nullable=True))

    # Backfill using Python normalization functions
    # Import here to avoid circular imports
    from app.utils.normalization import derive_key, normalize_display

    connection = op.get_bind()

    # Backfill products
    products = connection.execute(text("SELECT id, name FROM products")).fetchall()
    for product_id, name in products:
        name_display = normalize_display(name)
        name_key = derive_key(name)
        connection.execute(
            text(
                "UPDATE products SET name_raw = :raw, name_display = :display, name_key = :key WHERE id = :id"
            ),
            {"raw": name, "display": name_display, "key": name_key, "id": product_id}
        )

    # Backfill categories
    categories = connection.execute(text("SELECT id, name FROM categories")).fetchall()
    for category_id, name in categories:
        name_display = normalize_display(name)
        name_key = derive_key(name)
        connection.execute(
            text(
                "UPDATE categories SET name_raw = :raw, name_display = :display, name_key = :key WHERE id = :id"
            ),
            {"raw": name, "display": name_display, "key": name_key, "id": category_id}
        )


def downgrade() -> None:
    # Drop the three columns from products (in reverse order of creation)
    op.drop_column('products', 'name_key')
    op.drop_column('products', 'name_display')
    op.drop_column('products', 'name_raw')

    # Drop the three columns from categories (in reverse order of creation)
    op.drop_column('categories', 'name_key')
    op.drop_column('categories', 'name_display')
    op.drop_column('categories', 'name_raw')
