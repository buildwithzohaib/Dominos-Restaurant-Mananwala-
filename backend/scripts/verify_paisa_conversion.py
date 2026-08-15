#!/usr/bin/env python
"""Verify paisa conversion using Python Decimal (independent from SQL backfill)."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from sqlalchemy import text
from app.database import SessionLocal

db = SessionLocal()

print("[Starting] Verification - checking every row...")
print()
print("NULL HANDLING: NULL values must remain NULL (not become 0).")
print("Backfill used: SQL CAST(ROUND(x * 100) AS INTEGER)")
print("Verifier uses: Python int(Decimal(str(x)) * 100) [INDEPENDENT CHECK]")
print()

VERIFICATION_CHECKS = [
    ('products', 'price'),
    ('products', 'purchase_price'),
    ('orders', 'subtotal'),
    ('orders', 'discount'),
    ('orders', 'tax'),
    ('orders', 'total'),
    ('orders', 'amount_received'),
    ('orders', 'change_amount'),
    ('order_items', 'price'),
    ('order_items', 'line_total'),
    ('stock_movements', 'purchase_price'),
]

print("="*80)
print("VERIFICATION RESULTS")
print("="*80)
print()

total_rows_checked = 0
total_matched = 0
total_mismatched = 0

for table, old_col in VERIFICATION_CHECKS:
    new_col = f"{old_col}_paisa"

    # Query: get all rows for this column
    query = f"SELECT id, {old_col}, {new_col} FROM {table}"
    rows = db.execute(text(query)).fetchall()

    matched = 0
    mismatched = 0
    mismatches = []

    for row_id, old_val, new_val in rows:
        total_rows_checked += 1

        # NULL handling: NULL must stay NULL
        if old_val is None:
            if new_val is None:
                matched += 1
                total_matched += 1
            else:
                mismatched += 1
                total_mismatched += 1
                mismatches.append({
                    'id': row_id,
                    'old': None,
                    'new': new_val,
                    'expected': None,
                    'error': f'NULL converted to {new_val} (should stay NULL)',
                })
        else:
            # Non-NULL: old * 100 must equal new exactly
            expected = int(Decimal(str(old_val)) * 100)
            if new_val == expected:
                matched += 1
                total_matched += 1
            else:
                mismatched += 1
                total_mismatched += 1
                mismatches.append({
                    'id': row_id,
                    'old': str(old_val),
                    'new': new_val,
                    'expected': expected,
                    'diff': new_val - expected,
                })

    # Report this column
    print(f"{table:20} {old_col:20} : rows {len(rows):3d}, matched {matched:3d}, mismatched {mismatched:3d}", end="")

    if mismatched > 0:
        print(" [MISMATCH]")
        for m in mismatches:
            print(f"  id={m['id']}: old={m['old']}, new={m['new']}, expected={m['expected']}", end="")
            if 'diff' in m:
                print(f", diff={m['diff']}")
            else:
                print()
    else:
        print(" [OK]")

# Summary
print()
print("="*80)
print("VERIFICATION SUMMARY")
print("="*80)
print(f"Total columns checked    : {len(VERIFICATION_CHECKS)}")
print(f"Total rows checked       : {total_rows_checked}")
print(f"Total rows matched       : {total_matched}")
print(f"Total rows mismatched    : {total_mismatched}")
print()

if total_mismatched == 0:
    print("[OK] ALL ROWS VERIFIED - Conversion successful")
    print("[OK] Safe to proceed to Step 5 (Migration B)")
else:
    print(f"[FAIL] {total_mismatched} MISMATCHES FOUND")
    print("[FAIL] DO NOT PROCEED - Investigate differences")

print("="*80)

db.close()
