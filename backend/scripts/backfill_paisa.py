#!/usr/bin/env python
"""Backfill paisa columns from Numeric columns using SQL CAST(ROUND(...))."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import SessionLocal

db = SessionLocal()

print("[Starting] Backfill paisa columns...")
print()

# Define backfill SQL statements
# Using CAST(ROUND(value * 100) AS INTEGER) for SQL-level conversion
BACKFILL_STATEMENTS = [
    # Products
    (
        "products",
        """
        UPDATE products
        SET price_paisa = CAST(ROUND(price * 100) AS INTEGER)
        WHERE price IS NOT NULL
        """,
    ),
    (
        "products",
        """
        UPDATE products
        SET purchase_price_paisa = CAST(ROUND(purchase_price * 100) AS INTEGER)
        WHERE purchase_price IS NOT NULL
        """,
    ),
    # Orders
    (
        "orders",
        """
        UPDATE orders
        SET subtotal_paisa = CAST(ROUND(subtotal * 100) AS INTEGER)
        WHERE subtotal IS NOT NULL
        """,
    ),
    (
        "orders",
        """
        UPDATE orders
        SET discount_paisa = CAST(ROUND(discount * 100) AS INTEGER)
        WHERE discount IS NOT NULL
        """,
    ),
    (
        "orders",
        """
        UPDATE orders
        SET tax_paisa = CAST(ROUND(tax * 100) AS INTEGER)
        WHERE tax IS NOT NULL
        """,
    ),
    (
        "orders",
        """
        UPDATE orders
        SET total_paisa = CAST(ROUND(total * 100) AS INTEGER)
        WHERE total IS NOT NULL
        """,
    ),
    (
        "orders",
        """
        UPDATE orders
        SET amount_received_paisa = CAST(ROUND(amount_received * 100) AS INTEGER)
        WHERE amount_received IS NOT NULL
        """,
    ),
    (
        "orders",
        """
        UPDATE orders
        SET change_amount_paisa = CAST(ROUND(change_amount * 100) AS INTEGER)
        WHERE change_amount IS NOT NULL
        """,
    ),
    # OrderItems
    (
        "order_items",
        """
        UPDATE order_items
        SET price_paisa = CAST(ROUND(price * 100) AS INTEGER)
        WHERE price IS NOT NULL
        """,
    ),
    (
        "order_items",
        """
        UPDATE order_items
        SET line_total_paisa = CAST(ROUND(line_total * 100) AS INTEGER)
        WHERE line_total IS NOT NULL
        """,
    ),
    # StockMovements
    (
        "stock_movements",
        """
        UPDATE stock_movements
        SET purchase_price_paisa = CAST(ROUND(purchase_price * 100) AS INTEGER)
        WHERE purchase_price IS NOT NULL
        """,
    ),
]

for i, (table_name, sql) in enumerate(BACKFILL_STATEMENTS, 1):
    db.execute(text(sql))
    print(f"{i:2d}/11 - {table_name:<20} : backfilled")

db.commit()
print()
print("[OK] Backfill complete - all 11 columns updated")
db.close()
