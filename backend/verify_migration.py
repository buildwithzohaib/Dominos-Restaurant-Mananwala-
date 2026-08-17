#!/usr/bin/env python
"""Verify migration results."""
import sqlite3

db = sqlite3.connect('pos.db')

print("=" * 60)
print("MIGRATION VERIFICATION")
print("=" * 60)

# 1. Settings schema
print("\n1. SETTINGS TABLE SCHEMA (delivery_charge only):")
for row in db.execute("PRAGMA table_info(settings)"):
    if 'delivery' in row[1]:
        cid, name, type_, notnull, dflt, pk = row
        print(f"   Column: {name}, Type: {type_}, NOT NULL: {notnull}, Default: {dflt}")

# 2. Orders schema
print("\n2. ORDERS TABLE SCHEMA (delivery_charge only):")
for row in db.execute("PRAGMA table_info(orders)"):
    if 'delivery_charge' in row[1]:
        cid, name, type_, notnull, dflt, pk = row
        print(f"   Column: {name}, Type: {type_}, NOT NULL: {notnull}, Default: {dflt}")

# 3. Settings value
print("\n3. SETTINGS DELIVERY_CHARGE VALUE:")
val = db.execute("SELECT delivery_charge FROM settings").fetchone()
print(f"   {val[0]} paisa")

# 4. Orders distinct values
print("\n4. ORDERS DISTINCT DELIVERY_CHARGE VALUES:")
vals = db.execute("SELECT DISTINCT delivery_charge FROM orders ORDER BY delivery_charge").fetchall()
print(f"   {[v[0] for v in vals]}")

# 5. Order count
print("\n5. TOTAL ORDER COUNT:")
count = db.execute("SELECT COUNT(*) FROM orders").fetchone()
print(f"   {count[0]} orders")

# 6. Triggers
print("\n6. DELETE TRIGGER ON SETTINGS:")
trigger = db.execute(
    "SELECT name FROM sqlite_master WHERE type='trigger' AND name='prevent_settings_delete'"
).fetchone()
if trigger:
    print(f"   ✓ Trigger exists: {trigger[0]}")
else:
    print("   ✗ TRIGGER MISSING!")

# 7. All indexes
print("\n7. ALL INDEXES:")
indexes = db.execute(
    "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
).fetchall()
print(f"   Count: {len(indexes)}")
for idx in indexes:
    print(f"     {idx[0]}")

db.close()
