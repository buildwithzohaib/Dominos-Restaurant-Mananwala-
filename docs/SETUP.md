# Setup and Startup Order

**Important:** This document describes the correct initialization sequence when deploying a fresh database or starting the POS system.

## New Database Setup (First Time)

When setting up the restaurant POS on a new machine or with a fresh database, follow this **exact order**:

### 1. Run Database Migrations (Creates Schema)
```bash
cd backend
alembic upgrade head
```

This creates all tables (categories, products, orders, order_items, stock_movements, restaurant_tables) from the Alembic migration history. Schema is owned and versioned by Alembic, not by Python code.

**Why this step first:** The database schema must exist before any application code tries to read or write data.

### 2. Seed Initial Data (Populate Sample Data)
```bash
cd backend
python -m app.seed
```

This populates the database with:
- Default categories (Fast Food, Deals, Drinks)
- Sample products with prices and stock levels
- Default restaurant tables (6 tables)

**Why separate:** Seeding is a one-time setup step, not something that should run on every boot. This command is idempotent—running it multiple times is safe. It will skip products that already exist and backfill any missing metadata.

### 3. Start the Backend Server
```bash
cd backend
uvicorn app.main:app --reload
```

The app now starts clean: no automatic schema creation, no automatic seeding. It only loads routes and middleware.

### 4. Start the Frontend (in a separate terminal)
```bash
cd frontend
npm run dev
```

Browser opens at `http://localhost:5173`, backend API at `http://localhost:8000/api/...`

---

## Subsequent Boots (After Fresh Setup)

Once the database is initialized, simply start the backend and frontend:

```bash
cd backend
uvicorn app.main:app --reload

# In another terminal:
cd frontend
npm run dev
```

**Do NOT re-run seeding** unless you need to reset to default data. The seeding script is safe to run (idempotent), but unnecessary on normal operation.

---

## Why This Order?

**Before Task 0.6** (before this document), the startup was:
```python
# In backend/app/main.py on every boot:
Base.metadata.create_all(bind=engine)  # Create schema if missing
seed_data()  # Populate default data
```

This mixed concerns:
- Schema ownership was implicit (SQLAlchemy models)
- No versioning or rollback for schema changes
- Seeding ran on every boot, not just on fresh setup

**After Task 0.6**, schema creation is explicit:
- Alembic owns schema changes (git-tracked migrations)
- Seeding is a one-time setup command
- Import `app.main` is silent (no side effects)

This prevents bugs where:
- A fresh deployment would crash if migrations hadn't run yet
- Rolling back a migration would lose data silently
- Developers wouldn't know which schema version they had

---

## Settings Table

**Task 1.1:** The `settings` table holds the single immutable row that stores business configuration (restaurant name, currency symbol, tax rate, etc.). It is protected by three layers:
- CHECK constraint: `id = 1` (only id=1 allowed)
- PRIMARY KEY: prevents duplicate id=1
- DELETE trigger: `prevent_settings_delete` (prevents any deletion)

### Critical: DELETE Trigger Fragility

When SQLite rebuilds the `settings` table (e.g., adding a new column in a future migration), **the DELETE trigger may vanish silently**. This happened with indexes in Task 0.6 and 0.7.

**After any ALTER TABLE on the `settings` table**, verify the trigger exists:

```bash
sqlite3 backend/pos.db
SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name='prevent_settings_delete';
```

If the result is empty, recreate the trigger immediately:

```sql
CREATE TRIGGER prevent_settings_delete
BEFORE DELETE ON settings
BEGIN
  SELECT RAISE(ABORT, 'Cannot delete settings row');
END;
```

Then verify it was created:
```sql
SELECT name, sql FROM sqlite_master WHERE type='trigger';
```

### Column Defaults

The `settings` table has **no database-level column defaults** (no `server_default` in SQL). All columns have Python-level defaults in the model, and the row is pre-populated by the migration (INSERT statement).

**When adding a new NOT NULL column to `settings`:**
1. Use `server_default` on the new column (not just Python `default=`)
2. Or provide a value for the existing row in the migration
3. Without this, the existing row will fail the NOT NULL constraint

Example for Stage 3 (adding `delivery_charges`):
```python
op.add_column('settings', sa.Column('delivery_charges', sa.Integer(), nullable=False, server_default='0'))
```

---

## Troubleshooting

### "Table 'products' doesn't exist"
**Cause:** Alembic migrations were not run.  
**Fix:** Run `alembic upgrade head` from the `backend/` directory.

### "UNIQUE constraint failed: sku"
**This error should NOT occur in normal use.** The seed script is idempotent — it queries for existing products before inserting and skips duplicates.

**If you see this error, it indicates a real bug:**
- Something else is inserting duplicate products (e.g., concurrent requests, manual database manipulation, or a regression in the seed logic)
- Ignore the error at your peril; investigate the cause instead

**To diagnose:**
1. Check what products exist: `sqlite3 backend/pos.db "SELECT id, sku, name FROM products;"`
2. Look for duplicate SKUs
3. Check if `seed.py` was modified to skip the idempotency checks
4. Verify no other process is inserting products concurrently

**To reset and retry:**
1. Delete `backend/pos.db` (or back it up first)
2. Re-run the setup sequence: `alembic upgrade head && python -m app.seed`

### App starts but shows no data
**Cause:** Migrations ran but seeding didn't.  
**Fix:** Run `python -m app.seed` from the `backend/` directory.

---

**Last Updated:** 2026-08-16  
**Applies to:** Task 0.6 onwards (Task 1.1 added settings table documentation)
