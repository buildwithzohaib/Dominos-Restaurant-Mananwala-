# PROJECT: Restaurant POS System

## 1. CONTEXT

This is an existing Point-of-Sale application for a single-branch restaurant in Pakistan.
Phases 1-9 are already built. We are now building Phases 10-19, one task at a time.

Business setup (fixed — do not design for other cases):
- Single branch, single POS terminal
- Frontend and backend both run on the SAME machine. No internet dependency for daily operation.
- Order types: Dine-In (with tables), Takeaway, Delivery
- Currency: PKR. Tax/GST is currently DISABLED but the fields must exist in the schema
- Printing is browser-based (`window.print()` + print CSS) to an 80mm thermal receipt printer.
  There is NO separate kitchen printer and NO ESC/POS integration.
- Two-level inventory: products AND ingredients (recipes / BOM)

## 2. TECH STACK

**Frontend**
- React + TypeScript, built with Vite
- State: React Context API (existing `POSContext`)
- Styling: plain CSS
- Icons: `lucide-react`
- Package manager: npm

**Backend**
- Python + FastAPI, REST API
- SQLAlchemy ORM
- SQLite database
- Migrations: Alembic

**Printing**
- `window.print()` with CSS `@media print`
- 80mm thermal receipt layout (58mm must also be supported via settings)

**Commands**
```
Frontend:  npm run dev  |  npm run build  |  npm run test
Backend:   uvicorn app.main:app --reload  |  pytest
Migration: alembic revision --autogenerate -m "..."  |  alembic upgrade head
```

Do not introduce any new library or dependency without asking first and explaining
why the existing stack is not enough. Specifically: no new state management library,
no UI component library, no ORM other than SQLAlchemy, no ESC/POS printing library.

## 3. NON-NEGOTIABLE RULES

These are numbered. I will refer to them by number (e.g. "this violates Rule 4").

**RULE 1 — SINGLE SOURCE OF TRUTH**
Restaurant name, address, phone, logo, currency, tax rate, delivery charges, rounding
mode and business-day start ALL come from the settings record. Never hardcode any of
these anywhere, including receipts, headers, exports and reports.

**RULE 2 — NEVER SHOW DATABASE IDs IN THE UI**
No `category_id`, `product_id` or raw primary keys in any user-facing screen, form,
dropdown or receipt. Users see names, SKUs and order numbers only. IDs may exist in
API payloads and React props — just never rendered.

**RULE 3 — MONEY IS ALWAYS AN INTEGER**
Store all money as integer paisa (Rs. 1,250.00 => 125000). SQLAlchemy `Integer`
columns, TypeScript `number` treated as integer. Never use Float, Numeric, Decimal
or floating point arithmetic for money. Percentages are basis points integers
(16% => 1600). Format only at the display layer.

**RULE 4 — STOCK LEDGER IS APPEND-ONLY**
Never write directly to a `current_stock` column as the source of truth. Every stock
change creates a row in `stock_movements`. Those rows are immutable: never UPDATE,
never DELETE. To correct a mistake, insert a reversing movement. `current_stock` is a
cached value derived from the ledger.

**RULE 5 — `stock_movements` IS POLYMORPHIC**
It has `item_type` ('PRODUCT' | 'INGREDIENT') and `item_id`. Ingredients arrive in
Phase 15 and MUST use this same table. Never create a separate movements table for
ingredients.

**RULE 6 — NOTHING IS HARD-DELETED**
Products, categories, customers, ingredients, orders: use `is_active` / `voided`
flags. Deleting breaks historical reports and receipts.

**RULE 7 — ORDERS STORE SNAPSHOTS**
`order_items` must copy the product name and unit price at the time of sale, in
addition to the `product_id` foreign key. `delivery_details` must copy the customer
address text at the time of the order. Changing a price or an address later must never
change an old receipt.

**RULE 8 — STOCK DEDUCTS ON ORDER CONFIRM, NOT ON PAYMENT**
Dine-In: deduct per KOT batch when items are sent to kitchen.
Takeaway / Delivery: deduct when the order is confirmed.
Cart changes before confirm must NOT touch the ledger.
Voiding a confirmed item creates either a VOID_RETURN (back to stock) or a WASTAGE
movement — the user chooses.

**RULE 9 — TEXT NORMALIZATION**
Product / category / ingredient names are stored in three forms:
- `name_raw` — as typed, trimmed, multiple spaces collapsed
- `name_display` — Title Case, with an uppercase exception list (BBQ, XL, XXL, KG, ML, LTR, PC, PCS)
- `name_key` — lowercase, all spaces and symbols removed (used for duplicate checks)

Normalization is implemented ONCE, in Python, and is authoritative. Never auto-correct
spelling — only capitalization and spacing.

**RULE 10 — BUSINESS DAY, NOT CALENDAR DAY**
All daily reports use `settings.day_starts_at` (default 06:00). A sale at 01:30 AM
belongs to the previous business day. Timestamps are stored in UTC and displayed in
Asia/Karachi.

## 4. ARCHITECTURE CONVENTIONS

### Backend (FastAPI)
- Layering is strict: `routers/` (HTTP only) -> `services/` (business logic) -> `models/` (SQLAlchemy)
- Routers contain NO business logic. No queries, no calculations, no branching on
  business rules. They validate input, call a service, return a response.
- Pydantic schemas in `schemas/`, separate `Create` / `Update` / `Read` models
- Every schema change requires an Alembic migration. Never edit an existing migration.
- SQLite specifics: WAL mode enabled, `check_same_thread=False`, foreign keys pragma ON
- Any operation that writes more than one row (order confirm, recipe deduction, restore)
  must run inside a single transaction
- Tests with pytest, using an in-memory or temp-file SQLite database

### Frontend (React + TypeScript)
- No business logic in components. Components render and dispatch; logic lives in
  the API service layer or in hooks.
- All API calls go through the existing `api` service. No `fetch` calls inside components.
- TypeScript types for API payloads live in one `types/` module and must mirror the
  Pydantic schemas exactly. If you change a schema, update the type in the same task.
- Context split: keep `SettingsContext` separate from `POSContext`. Settings change
  rarely; cart changes constantly. Putting them together re-renders the whole product
  grid on every cart tap.
- Money is formatted only via `formatMoney()`. Never inline `toFixed` or string concat.
- Icons: `lucide-react` only.

### Printing
- Print output is produced by dedicated React components (`<ReceiptPrint>`,
  `<KitchenSlipPrint>`, `<ZReportPrint>`) rendered into a hidden container and
  revealed only inside `@media print`.
- Print CSS uses `@page { size: 80mm auto; margin: 0; }` (58mm variant driven by
  the settings value), monospace font, no colors, no background images.
- `@media print` must hide the entire app shell — sidebar, headers, buttons.
- Printing must never block or lose data: the order is saved first, printing second.
  If printing fails, show a retry button.

### General
- No placeholder code, no TODO stubs, no mock or fake data in production paths.
  If you cannot complete something, say so instead of writing a stub.
- Comments only where the "why" is non-obvious. Do not comment obvious code.
- UI text is in English.

## 5. HOW YOU MUST WORK

For every task I give you:

**STEP 1 — Before writing any code, reply with a short PLAN:**
- a) Files you will create or modify (exact paths, backend and frontend)
- b) Schema changes and the Alembic migration needed
- c) The approach in 3-6 bullet points
- d) Anything ambiguous that you need me to decide

Then STOP and wait for my approval.

**STEP 2 — After I approve, implement it.**

**STEP 3 — After implementing, reply with:**
- a) List of files changed
- b) Commands I need to run (migrations, npm install, etc.)
- c) Exact manual steps for me to verify it works in the running app
- d) Anything you did NOT do that the task mentioned

## 6. HARD LIMITS

- Do not modify files outside the scope of the current task.
- Do not refactor unrelated code, even if you think it is bad. Tell me instead.
- Do not remove or rewrite existing working features.
- Do not change the database schema without an Alembic migration.
- Do not guess at business rules. If the spec does not cover it, ask me.
- Do not duplicate business logic between Python and TypeScript. Backend is
  authoritative for calculations; the frontend displays what the API returns.
- If a request conflicts with Rules 1-10, stop and tell me which rule it breaks.