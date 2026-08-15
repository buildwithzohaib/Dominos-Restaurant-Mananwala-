#!/usr/bin/env python
"""Backfill paisa columns from Numeric columns using SQL CAST(ROUND(...)).

Takes database path as command-line argument.
Creates its own engine and session without using app.database.
Runs the EXACT same 11 UPDATE statements as backfill_paisa.py.
"""

import sys
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

if len(sys.argv) < 2:
    print("Usage: python backfill_paisa_at.py <database_path>")
    sys.exit(1)

db_path = sys.argv[1]

# Resolve to absolute path
absolute_path = os.path.abspath(db_path)

# Check if file exists
if not os.path.exists(absolute_path):
    print(f"Error: Database file not found: {absolute_path}")
    sys.exit(1)

print(f"[Starting] Backfill paisa columns...")
print(f"[Database] {absolute_path}")
print()

# Create engine and session for the specified database
engine = create_engine(f"sqlite:///{absolute_path}", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
db = Session()

# Define backfill SQL statements — COPIED VERBATIM from backfill_paisa.py
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
