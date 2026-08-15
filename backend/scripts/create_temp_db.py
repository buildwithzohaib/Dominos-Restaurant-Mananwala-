#!/usr/bin/env python
"""Create empty temp databases for Alembic setup."""

import sqlite3
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))

# Create tmp_empty.db for autogenerate
empty_db = os.path.join(backend_dir, "tmp_empty.db")
if os.path.exists(empty_db):
    os.remove(empty_db)
conn = sqlite3.connect(empty_db)
conn.close()
print(f"[OK] Created {empty_db}")

# Create tmp_verify.db for verification
verify_db = os.path.join(backend_dir, "tmp_verify.db")
if os.path.exists(verify_db):
    os.remove(verify_db)
conn = sqlite3.connect(verify_db)
conn.close()
print(f"[OK] Created {verify_db}")
