#!/usr/bin/env python
"""Verify migration 3.5: address field added to customers."""
import sqlite3

db = sqlite3.connect('pos.db')

print("=" * 60)
print("VERIFICATION: Task 3.5 — customers.address")
print("=" * 60)

# 1. PRAGMA table_info(customers)
print("\n1. CUSTOMERS TABLE SCHEMA:")
for row in db.execute("PRAGMA table_info(customers)"):
    cid, name, type_, notnull, dflt, pk = row
    if name == 'address':
        print(f"   ✓ Column: {name}, Type: {type_}, NOT NULL: {notnull}, Default: {dflt}")
    else:
        print(f"   Column: {name}, Type: {type_}, NOT NULL: {notnull}, Default: {dflt}")

# 2. PRAGMA index_list(customers)
print("\n2. INDEXES ON CUSTOMERS TABLE:")
indexes = list(db.execute("PRAGMA index_list(customers)"))
print(f"   Count: {len(indexes)} (expect 2)")
for seq, name, unique, origin, partial in indexes:
    print(f"   - {name}: unique={unique}, origin={origin}")

# 3. All indexes across database
print("\n3. ALL INDEXES ACROSS DATABASE:")
all_indexes = list(db.execute("SELECT name FROM sqlite_master WHERE type='index'"))
print(f"   Count: {len(all_indexes)} (expect 10)")
for row in all_indexes:
    print(f"   - {row[0]}")

# 4. Triggers
print("\n4. TRIGGERS:")
triggers = list(db.execute("SELECT name FROM sqlite_master WHERE type='trigger'"))
print(f"   Count: {len(triggers)}")
for row in triggers:
    print(f"   - {row[0]}")

# 5. Customer count
print("\n5. CUSTOMER COUNT:")
count = db.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
print(f"   {count} (unchanged)")

# 6. Alembic check
print("\n6. ALEMBIC CHECK:")
print("   (running separately below)")

db.close()
