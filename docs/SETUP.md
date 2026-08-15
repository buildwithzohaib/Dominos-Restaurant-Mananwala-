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

## Troubleshooting

### "Table 'products' doesn't exist"
**Cause:** Alembic migrations were not run.  
**Fix:** Run `alembic upgrade head` from the `backend/` directory.

### "UNIQUE constraint failed: sku"
**Cause:** Trying to seed when products already exist.  
**Fix:** This is OK. The seed script skips existing products. If you want to reset, delete `backend/pos.db` and re-run the setup sequence.

### App starts but shows no data
**Cause:** Migrations ran but seeding didn't.  
**Fix:** Run `python -m app.seed` from the `backend/` directory.

---

**Last Updated:** 2026-08-15  
**Applies to:** Task 0.6 onwards
