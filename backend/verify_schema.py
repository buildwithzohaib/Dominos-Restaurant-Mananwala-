#!/usr/bin/env python3
"""
Schema verification script for Phase 11 migrations.
Verifies that product_type, deal_components, order_item_components tables exist
and that OrderItem has deal_id and price_override columns.
"""
import sqlite3
import sys

def verify_schema():
    db_path = r"C:\dev\my-pos\backend\pos.db"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("=" * 60)
        print("SCHEMA VERIFICATION FOR PHASE 11")
        print("=" * 60)

        # Check 1: product_type column on products table
        print("\n[1] Checking product_type column on products table...")
        cursor.execute("PRAGMA table_info(products)")
        columns = [row[1] for row in cursor.fetchall()]
        if "product_type" in columns:
            print("    ✓ product_type column exists")
            # Get the default value
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='products'")
            create_sql = cursor.fetchone()[0]
            if "'PRODUCT'" in create_sql or '"PRODUCT"' in create_sql:
                print("    ✓ product_type defaults to 'PRODUCT'")
            else:
                print("    ⚠ Could not confirm default value from schema")
        else:
            print("    ✗ product_type column NOT found")
            return False

        # Check 2: deal_components table exists
        print("\n[2] Checking deal_components table...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deal_components'")
        if cursor.fetchone():
            print("    ✓ deal_components table exists")
            cursor.execute("PRAGMA table_info(deal_components)")
            cols = {row[1]: row[2] for row in cursor.fetchall()}
            required = ['id', 'product_id', 'component_product_id', 'quantity', 'size_id', 'sort_order']
            for col in required:
                if col in cols:
                    print(f"    ✓ Column {col} exists")
                else:
                    print(f"    ✗ Column {col} NOT found")
                    return False
        else:
            print("    ✗ deal_components table NOT found")
            return False

        # Check 3: order_item_components table exists
        print("\n[3] Checking order_item_components table...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='order_item_components'")
        if cursor.fetchone():
            print("    ✓ order_item_components table exists")
            cursor.execute("PRAGMA table_info(order_item_components)")
            cols = {row[1]: row[2] for row in cursor.fetchall()}
            required = ['id', 'order_item_id', 'deal_component_id', 'product_id', 'product_name',
                       'quantity', 'size_id', 'was_removed', 'removed_reason', 'created_at']
            for col in required:
                if col in cols:
                    print(f"    ✓ Column {col} exists")
                else:
                    print(f"    ✗ Column {col} NOT found")
                    return False
        else:
            print("    ✗ order_item_components table NOT found")
            return False

        # Check 4: deal_id and price_override on order_items
        print("\n[4] Checking deal_id and price_override columns on order_items...")
        cursor.execute("PRAGMA table_info(order_items)")
        cols = {row[1]: row[2] for row in cursor.fetchall()}
        if "deal_id" in cols:
            print("    ✓ deal_id column exists")
        else:
            print("    ✗ deal_id column NOT found")
            return False
        if "price_override" in cols:
            print("    ✓ price_override column exists")
        else:
            print("    ✗ price_override column NOT found")
            return False

        # Check 5: Foreign keys
        print("\n[5] Checking foreign key constraints...")
        cursor.execute("PRAGMA foreign_key_list(deal_components)")
        fks = cursor.fetchall()
        print(f"    deal_components FKs: {len(fks)} found")

        cursor.execute("PRAGMA foreign_key_list(order_item_components)")
        fks = cursor.fetchall()
        print(f"    order_item_components FKs: {len(fks)} found")

        print("\n" + "=" * 60)
        print("✓ ALL SCHEMA CHECKS PASSED")
        print("=" * 60)
        conn.close()
        return True

    except Exception as e:
        print(f"\n✗ ERROR: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    success = verify_schema()
    sys.exit(0 if success else 1)
