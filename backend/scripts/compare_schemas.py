#!/usr/bin/env python
"""Compare schemas (tables and indexes) between tmp_verify.db and pos.db."""

import sqlite3
import re


def get_schema_tables(db_path):
    """Extract all table definitions, sorted and normalized."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all CREATE TABLE statements, excluding sqlite_sequence and alembic_version
    cursor.execute("""
        SELECT name, sql FROM sqlite_master
        WHERE type='table'
        AND name NOT IN ('sqlite_sequence', 'alembic_version')
        ORDER BY name
    """)

    tables = {}
    for name, sql in cursor.fetchall():
        if sql:
            # Normalize: remove extra whitespace and trailing commas
            normalized = re.sub(r'\s+', ' ', sql).strip()
            normalized = re.sub(r',\s*\)', ')', normalized)
            tables[name] = normalized

    conn.close()
    return tables


def get_indexes(db_path):
    """Extract all indexes with details."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all indexes from sqlite_master
    cursor.execute("""
        SELECT name, sql FROM sqlite_master
        WHERE type='index'
        AND name NOT LIKE 'sqlite_autoindex_%'
        AND sql IS NOT NULL
        ORDER BY name
    """)

    index_sqls = cursor.fetchall()
    indexes = {}
    for name, sql in index_sqls:
        # Skip alembic_version indexes
        if 'alembic_version' in sql:
            continue
        is_unique = 'UNIQUE' in sql.upper()
        indexes[name] = {'sql': sql, 'unique': is_unique}

    conn.close()
    return indexes


# Get schemas
print("[OK] Running comprehensive schema comparison...")
print()

verify_tables = get_schema_tables("tmp_verify.db")
real_tables = get_schema_tables("pos.db")

verify_indexes = get_indexes("tmp_verify.db")
real_indexes = get_indexes("pos.db")

print("="*80)
print("COMPREHENSIVE SCHEMA COMPARISON: tmp_verify.db vs pos.db")
print("="*80)
print()

# ============================================================================
# TABLE COMPARISON
# ============================================================================
print("PART 1: TABLE DEFINITIONS")
print("-"*80)

all_tables = set(list(verify_tables.keys()) + list(real_tables.keys()))
print(f"Tables found: {sorted(all_tables)}")
print()

verify_only = set(verify_tables.keys()) - set(real_tables.keys())
real_only = set(real_tables.keys()) - set(verify_tables.keys())

if verify_only:
    print(f"[WARN] Tables only in tmp_verify.db: {sorted(verify_only)}")
if real_only:
    print(f"[WARN] Tables only in pos.db: {sorted(real_only)}")

if not verify_only and not real_only:
    print("[OK] Both databases have the same tables")
print()

table_mismatches = 0
for table_name in sorted(all_tables):
    verify_sql = verify_tables.get(table_name, "[NOT FOUND]")
    real_sql = real_tables.get(table_name, "[NOT FOUND]")

    if verify_sql == real_sql:
        print(f"[OK] {table_name}")
    else:
        print(f"[MISMATCH] {table_name}")
        table_mismatches += 1

print()

# ============================================================================
# INDEX COMPARISON
# ============================================================================
print("PART 2: INDEXES")
print("-"*80)

all_indexes = set(list(verify_indexes.keys()) + list(real_indexes.keys()))
print(f"Indexes found: {sorted(all_indexes)}")
print()

verify_only_idx = set(verify_indexes.keys()) - set(real_indexes.keys())
real_only_idx = set(real_indexes.keys()) - set(verify_indexes.keys())

if verify_only_idx:
    print(f"[WARN] Indexes only in tmp_verify.db: {sorted(verify_only_idx)}")
    for idx in sorted(verify_only_idx):
        print(f"       {idx}")
if real_only_idx:
    print(f"[WARN] Indexes only in pos.db: {sorted(real_only_idx)}")
    for idx in sorted(real_only_idx):
        print(f"       {idx}")

if not verify_only_idx and not real_only_idx:
    print("[OK] Both databases have the same indexes")
print()

index_mismatches = 0
for idx_name in sorted(all_indexes):
    if idx_name in verify_only_idx or idx_name in real_only_idx:
        continue  # Already reported above

    verify_info = verify_indexes.get(idx_name, {})
    real_info = real_indexes.get(idx_name, {})

    verify_sql = verify_info.get('sql', '[NOT FOUND]')
    verify_unique = verify_info.get('unique', None)
    real_sql = real_info.get('sql', '[NOT FOUND]')
    real_unique = real_info.get('unique', None)

    if verify_sql == real_sql and verify_unique == real_unique:
        unique_flag = "(UNIQUE)" if verify_unique else ""
        print(f"[OK] {idx_name} {unique_flag}")
    else:
        print(f"[MISMATCH] {idx_name}")
        if verify_unique != real_unique:
            print(f"  unique flag mismatch: verify={verify_unique}, pos.db={real_unique}")
        if verify_sql != real_sql:
            print(f"  SQL mismatch")
            print(f"    verify: {verify_sql[:80]}...")
            print(f"    pos.db: {real_sql[:80]}...")
        index_mismatches += 1

print()

# ============================================================================
# SUMMARY
# ============================================================================
print("="*80)
print("SUMMARY")
print("="*80)
print(f"Tables: {len(all_tables)} total")
if table_mismatches == 0:
    print(f"  [OK] All table definitions match")
else:
    print(f"  [FAIL] {table_mismatches} mismatches")

print(f"Indexes: {len(all_indexes)} total")
if index_mismatches == 0 and not verify_only_idx and not real_only_idx:
    print(f"  [OK] All indexes match")
else:
    print(f"  [FAIL] {index_mismatches} mismatches + {len(verify_only_idx)} only in verify + {len(real_only_idx)} only in pos.db")

print()
if table_mismatches == 0 and index_mismatches == 0 and not verify_only_idx and not real_only_idx:
    print("[OK] ROUND-TRIP VERIFICATION PASSED - All schemas identical")
else:
    print("[FAIL] ROUND-TRIP VERIFICATION FAILED - Differences exist")
print("="*80)
