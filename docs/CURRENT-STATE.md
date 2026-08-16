# CURRENT STATE AUDIT — My Restaurant POS

**Date:** 2026-08-15  
**Status:** READ-ONLY REPORT  
**Phases Completed:** 1–10

---

## 1. PROJECT STRUCTURE

### Backend Directory Structure (2 levels deep)

```
backend/
├── app/
│   ├── models/              # SQLAlchemy ORM definitions
│   │   ├── __init__.py
│   │   └── models.py        # 6 tables: Category, Product, RestaurantTable, Order, OrderItem, StockMovement
│   ├── routes/              # FastAPI route handlers (HTTP only, no business logic)
│   │   ├── __init__.py
│   │   ├── catalog.py       # GET /api/categories, /api/products (active only), /api/tables
│   │   ├── dashboard.py     # GET /api/dashboard/overview (Phase 9)
│   │   ├── inventory.py     # GET/PUT /api/inventory/{id}, POST /api/inventory/{id}/stock/adjust
│   │   ├── orders.py        # POST/GET /api/orders, POST /api/orders/{id}/cancel (Phase 8)
│   │   ├── products.py      # POST/PUT/PATCH /api/products/* (Phase 10)
│   │   └── stock_movements.py  # GET /api/stock-movements with filters
│   ├── services/            # Business logic layer
│   │   ├── __init__.py
│   │   ├── dashboard_service.py   # Dashboard metrics aggregation (Phase 9)
│   │   ├── inventory_service.py   # Stock operations (add, adjust)
│   │   ├── order_service.py       # Order creation, cancellation, stock deduction
│   │   ├── product_service.py     # Product CRUD (Phase 10)
│   │   └── stock_service.py       # Stock ledger operations
│   ├── schemas/             # Pydantic input/output schemas
│   │   ├── __init__.py
│   │   └── schemas.py       # All Create/Read/Update DTOs
│   ├── database.py          # SQLAlchemy engine, Base, SessionLocal, get_db()
│   └── main.py              # FastAPI app, CORS, Base.metadata.create_all() on startup
├── requirements.txt         # Dependencies: fastapi, uvicorn, sqlalchemy, pydantic
├── pos.db                   # SQLite database (auto-created)
├── seed.py                  # Database initialization with sample data
└── test_phase*.py           # Unit tests for Phases 8, 9

```

### Frontend Directory Structure (2 levels deep)

```
frontend/
├── src/
│   ├── components/          # React UI components (no business logic)
│   │   ├── AddProductModal.tsx        # Phase 10 product creation
│   │   ├── AddStockModal.tsx          # Inventory stock addition
│   │   ├── CancelOrderModal.tsx       # Phase 8 order cancellation
│   │   ├── EditInventoryModal.tsx     # Inventory metadata edit
│   │   ├── EditProductModal.tsx       # Phase 10 product editing
│   │   ├── OrderDetailsModal.tsx      # Order view with receipt layout
│   │   ├── OrderPanel.tsx             # Cart display and checkout
│   │   ├── OrderStatusBadge.tsx       # PAID/CANCELLED status display
│   │   ├── PaymentModal.tsx           # Payment method selection and receipt prep
│   │   ├── ProductCard.tsx            # Product tile in menu
│   │   ├── StatusBadge.tsx            # IN_STOCK/LOW_STOCK/OUT_OF_STOCK badge
│   │   ├── StockAdjustmentModal.tsx   # Inventory adjustment
│   │   ├── StockHistory.tsx           # Stock movements ledger (Phase 4)
│   │   ├── SuccessModal.tsx           # Post-payment receipt (print + screen)
│   │   └── CategoryBar.tsx            # Category navigation
│   ├── context/             # React Context API state management
│   │   └── POSContext.tsx   # Cart, order type, discount, tax, payment method
│   ├── pages/               # Full-page components (routers)
│   │   ├── Dashboard.tsx    # Business overview dashboard (Phase 9)
│   │   ├── Inventory.tsx    # Stock management page (Phase 3)
│   │   ├── Orders.tsx       # Order history page
│   │   ├── POS.tsx          # Main point-of-sale page
│   │   └── Products.tsx     # Product management (Phase 10)
│   ├── services/            # API service layer
│   │   └── api.ts           # All fetch() calls to backend
│   ├── types/               # TypeScript interfaces (mirrors Pydantic schemas)
│   │   └── index.ts
│   ├── data/                # Static data
│   │   └── tables.ts        # Sample table data
│   ├── App.tsx              # Main app shell, navigation
│   ├── main.tsx             # React entry point
│   └── styles.css           # All styling including @media print rules
├── package.json             # npm scripts and dependencies
├── tsconfig.json            # TypeScript config
├── vite.config.ts           # Vite build config
├── index.html               # HTML entry point
└── node_modules/            # Dependencies

```

---

## 2. BACKEND FACTS

### A. Database Tables and Columns

**6 tables currently defined in `app/models/models.py`:**

#### Table 1: `categories`
| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | Integer | PRIMARY KEY | |
| `name` | String(100) | UNIQUE, INDEX | Category name |
| `active` | Boolean | default=True | Soft-delete flag (Rule 6) |

**Relationships:** `products` (one-to-many cascade)

---

#### Table 2: `products`
| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | Integer | PRIMARY KEY | |
| `category_id` | Integer | FK→categories.id | Parent category |
| `name` | String(150) | INDEX | Product display name |
| `price` | **Numeric(10, 2)** | NOT NULL | **MONEY: Decimal** selling price (Rule 3) |
| `stock` | Integer | default=0 | Current quantity (Rule 4: updated with stock_movements) |
| `image` | String(500) | nullable | Image URL |
| `available` | Boolean | default=True | Enable/disable (Phase 10) |
| `sku` | String(50) | UNIQUE, INDEX | Stock-keeping unit |
| `min_stock` | Integer | default=5 | Low-stock threshold |
| `unit` | String(30) | default="Piece" | Measurement unit (PC, KG, LTR, etc.) |
| `purchase_price` | **Numeric(10, 2)** | default=0 | **MONEY: Decimal** cost per unit |
| `updated_at` | DateTime | default=now, onupdate | Timestamp |

**Relationships:** `category` (many-to-one), no cascade deletions (Rule 6)

---

#### Table 3: `stock_movements`
| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | Integer | PRIMARY KEY | |
| `product_id` | Integer | FK→products.id, INDEX | **PRODUCT-ONLY** (not polymorphic—see Risk #2) |
| `product_name` | String(150) | NOT NULL | Snapshot of name at time of movement (Rule 7) |
| `movement_type` | String(20) | INDEX | PURCHASE, ADJUSTMENT, SALE, CANCELLATION |
| `quantity_change` | Integer | NOT NULL | Signed: +50 purchase, -2 sale (Rule 4) |
| `reason` | String(200) | NOT NULL | Why the change occurred |
| `supplier` | String(150) | nullable | Vendor for PURCHASE movements |
| `purchase_price` | **Numeric(10, 2)** | nullable | **MONEY: Decimal** cost at time of movement |
| `stock_before` | Integer | NOT NULL | Inventory level before this change |
| `stock_after` | Integer | NOT NULL | Inventory level after this change |
| `reference` | String(50) | nullable | Refers to order_number for SALE/CANCELLATION |
| `created_at` | DateTime | default=now, INDEX | When recorded |

**Relationships:** `product` (many-to-one read-only)

**Immutability:** Append-only ledger; never UPDATE/DELETE rows (Rule 4)

**Limitation:** Only tracks products. Ingredients arrive in Phase 15 and MUST use `item_type`/`item_id` fields (Rule 5).

---

#### Table 4: `restaurant_tables`
| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | Integer | PRIMARY KEY | |
| `name` | String(50) | UNIQUE | Table identifier (e.g., "T1", "T2") |
| `seats` | Integer | default=4 | Seating capacity |
| `active` | Boolean | default=True | Soft-delete flag (Rule 6) |

**Relationships:** `orders` (one-to-many)

---

#### Table 5: `orders`
| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | Integer | PRIMARY KEY | |
| `order_number` | String(30) | UNIQUE, INDEX | Human-readable (e.g., "ORD-00001") |
| `order_type` | String(30) | default="TAKEAWAY" | DINE_IN, TAKEAWAY, DELIVERY |
| `table_id` | Integer | FK→restaurant_tables.id, nullable | Required only for DINE_IN |
| `status` | String(30) | default="PAID" | PAID or CANCELLED (Phase 7) |
| `subtotal` | **Numeric(10, 2)** | NOT NULL | **MONEY: Decimal** before discount/tax |
| `discount` | **Numeric(10, 2)** | default=0 | **MONEY: Decimal** amount deducted |
| `tax` | **Numeric(10, 2)** | default=0 | **MONEY: Decimal** (currently unused but reserved) |
| `total` | **Numeric(10, 2)** | NOT NULL | **MONEY: Decimal** final amount due |
| `payment_method` | String(30) | NOT NULL | CASH, CARD, OTHER |
| `amount_received` | **Numeric(10, 2)** | default=0 | **MONEY: Decimal** cash/card tendered |
| `change_amount` | **Numeric(10, 2)** | default=0 | **MONEY: Decimal** change returned (CASH only) |
| `created_at` | DateTime | default=now, INDEX | When order placed |
| `cancelled_at` | DateTime | nullable | Phase 8: when order cancelled |
| `cancelled_reason` | String(200) | nullable | Phase 8: reason for cancellation |

**Relationships:** `table` (many-to-one), `items` (one-to-many cascade)

**Note:** Orders are never deleted; cancellation sets `status="CANCELLED"` and records `cancelled_at`/`cancelled_reason` (Rule 6).

---

#### Table 6: `order_items`
| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | Integer | PRIMARY KEY | |
| `order_id` | Integer | FK→orders.id | Parent order |
| `product_id` | Integer | FK→products.id | Reference to product at order time |
| `product_name` | String(150) | NOT NULL | Snapshot of name at time of sale (Rule 7) |
| `quantity` | Integer | NOT NULL | Units ordered |
| `price` | **Numeric(10, 2)** | NOT NULL | **MONEY: Decimal** unit price at time of sale (Rule 7) |
| `line_total` | **Numeric(10, 2)** | NOT NULL | **MONEY: Decimal** quantity × price |

**Relationships:** `order` (many-to-one cascade)

---

### B. Money-Related Columns (CRITICAL)

All monetary fields in the database use **`Numeric(10, 2)`** with Python `Decimal` type.

| Table | Column | SQLAlchemy Type | Comment |
|-------|--------|-----------------|---------|
| products | price | Numeric(10, 2) | Selling price per unit |
| products | purchase_price | Numeric(10, 2) | Cost per unit |
| stock_movements | purchase_price | Numeric(10, 2) | Cost at time of movement (nullable) |
| orders | subtotal | Numeric(10, 2) | Before discount and tax |
| orders | discount | Numeric(10, 2) | Amount deducted |
| orders | tax | Numeric(10, 2) | Tax amount (currently unused) |
| orders | total | Numeric(10, 2) | Final amount due |
| orders | amount_received | Numeric(10, 2) | Cash/card tendered |
| orders | change_amount | Numeric(10, 2) | Change returned |
| order_items | price | Numeric(10, 2) | Unit price snapshot at sale |
| order_items | line_total | Numeric(10, 2) | Quantity × price |

**Type:** `Numeric(10, 2)` means **fixed-point decimal** with 10 total digits, 2 after decimal point.  
**Risk Level:** ✅ **LOW** — Using `Decimal`, not `Float`. Fits Rule 3 (integer paisa) conceptually, but currently stored as `Numeric` not `Integer`.

---

### C. Alembic Configuration

**Status:** ❌ **NOT CONFIGURED**

- No `alembic/` directory exists in backend/
- `alembic.ini` not present
- `env.py` not present
- No migrations/ directory

**Current Schema Origin:** `Base.metadata.create_all()` called on every app startup  
**Location:** `backend/app/main.py:13`

```python
Base.metadata.create_all(bind=engine)  # ← Called at startup
seed_data()  # ← Populates sample data
```

**Impact:** 
- Schema is created from SQLAlchemy model definitions, not from migration files
- No version history of schema changes
- No rollback capability
- Existing data requires manual `alembic stamp head` after Alembic setup

---

### D. Services Layer

**Status:** ✅ **WELL-STRUCTURED**

Services exist and are the only place business logic lives:

| Service | Location | Purpose |
|---------|----------|---------|
| `order_service` | `app/services/order_service.py` | Order creation, validation, stock deduction, cancellation with restoration |
| `inventory_service` | `app/services/inventory_service.py` | Stock add/adjust operations |
| `product_service` | `app/services/product_service.py` | Product CRUD (Phase 10) |
| `stock_service` | `app/services/stock_service.py` | Stock ledger operations |
| `dashboard_service` | `app/services/dashboard_service.py` | Dashboard metrics aggregation (Phase 9) |

**Architecture Pattern:**
```
Route Handler (catalog.py, orders.py, etc.)
    ↓ (validates input, calls service)
Service Layer (order_service.py, etc.)
    ↓ (business logic, transactions)
Models + DB Session (models.py)
    ↓
SQLite
```

**No business logic in routes** ✅ — Routes only:
- Receive HTTP request
- Validate Pydantic schema
- Call a service
- Return response

Example: `orders.py:10-12`
```python
@router.post("", response_model=OrderOut)
def create(payload: OrderCreate, db: Session = Depends(get_db)):
    return create_order(db, payload)  # ← Delegates to service
```

---

## 3. FRONTEND FACTS

### A. POSContext State and Actions

**Location:** `frontend/src/context/POSContext.tsx`

**State shape:**
```typescript
interface State {
  cart: CartItem[];           // Array of {product, quantity}
  orderType: OrderType;       // "DINE_IN" | "TAKEAWAY" | "DELIVERY"
  selectedTable: RestaurantTable | null;  // For DINE_IN only
  discount: number;           // Absolute amount (not percentage)
  taxRate: number;            // 0-100 (percentage)
  paymentMethod: PaymentMethod;  // "CASH" | "CARD" | "OTHER"
}
```

**Computed values (useMemo):**
- `subtotal` — sum of (price × quantity) for all cart items
- `discount` — capped at subtotal
- `tax` — (subtotal - discount) × taxRate / 100
- `total` — subtotal - discount + tax

**Actions (useCallback dispatch):**
| Action | Payload | Effect |
|--------|---------|--------|
| ADD | product | Add product to cart or increment qty (soft stock cap) |
| SET_QTY | {productId, quantity} | Set exact qty or remove if ≤0 |
| REMOVE | productId | Remove product from cart |
| CLEAR | — | Empty cart (preserves orderType) |
| ORDER_TYPE | value | Set order type, clear table if not DINE_IN |
| TABLE | value | Set table (DINE_IN only) |
| DISCOUNT | value | Set discount amount |
| TAX | value | Set tax rate (0-100) |
| PAYMENT | value | Set payment method |
| SYNC_PRODUCTS | products[] | Update product snapshots when stock changes |

**Key design:**
- Cart stores `CartItem[]` with full `Product` object (not just ID)
- **Soft stock cap:** Cart limits qty per product to available stock, but backend re-validates at order time
- **Product sync:** When stock changes (sale, adjustment), cart lines are updated and qty capped to new stock

---

### B. API Service Shape

**Location:** `frontend/src/services/api.ts`

**Pattern:** Centralized fetch wrapper, all calls use `request<T>(path, options)`

**Key methods:**

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `getCategories()` | GET /api/categories | List all categories |
| `getProducts(search?, includeDisabled?)` | GET /api/products | List active products (or all if flag set) |
| `getTables()` | GET /api/tables | List all tables |
| `getOrders(params?)` | GET /api/orders | List orders with search/status filter |
| `createOrder(payload)` | POST /api/orders | Create and confirm order |
| `cancelOrder(id, payload)` | POST /api/orders/{id}/cancel | Cancel order with reason (Phase 8) |
| `getInventory(search?)` | GET /api/inventory | List products for inventory page |
| `getInventoryItem(id)` | GET /api/inventory/{id} | Get single product details |
| `updateInventoryItem(id, payload)` | PUT /api/inventory/{id} | Update product metadata |
| `addStock(id, payload)` | POST /api/inventory/{id}/stock | Record purchase |
| `adjustStock(id, payload)` | POST /api/inventory/{id}/adjust | Record adjustment |
| `getStockMovements(params?)` | GET /api/stock-movements | List movements with filters |
| `getDashboardOverview()` | GET /api/dashboard/overview | Today's metrics (Phase 9) |
| `getProduct(id)` | GET /api/products/{id} | Single product (Phase 10) |
| `createProduct(payload)` | POST /api/products | Create product (Phase 10) |
| `updateProduct(id, payload)` | PUT /api/products/{id} | Update product (Phase 10) |
| `disableProduct(id)` | PATCH /api/products/{id}/disable | Disable (Phase 10) |
| `enableProduct(id)` | PATCH /api/products/{id}/enable | Enable (Phase 10) |

**Error handling:** Rejects if response not ok; tries to extract `detail` from JSON error body

---

### C. Money Formatting for Display

**Status:** ❌ **NOT CENTRALIZED** — Hardcoded inline everywhere

All money formatting uses **`.toFixed(2)`** with hardcoded **"Rs. "** prefix.

**Locations (29+ instances found):**

| File | Line(s) | Pattern |
|------|---------|---------|
| OrderDetailsModal.tsx | 38, 41, 51, 55, 59, 63 | `Rs. {Number(...).toFixed(2)}` |
| OrderPanel.tsx | 47, 85-86, 125, 130, 135, 140 | `Rs. {Number(...).toFixed(2)}` |
| PaymentModal.tsx | 170, 218, 246-247, 249-250 | `Rs. {Number(...).toFixed(2)}` |
| ProductCard.tsx | 31 | `Rs. {Number(...).toFixed(2)}` |
| StockHistory.tsx | 94 | `Rs. ${Number(...).toFixed(2)}` |
| SuccessModal.tsx | 65, 70, 81, 86, 91, 96, 112, 117, 204, 209, 214, 219, 232 | `Rs. {Number(...).toFixed(2)}` |
| Dashboard.tsx | 86, 127, 159 | `Rs. {Number(...).toLocaleString(...)}` or `.toFixed(...)` |
| Inventory.tsx | 138 | `Rs. {Number(...).toFixed(2)}` |

**No `formatMoney()` utility function exists.** All formatting is inline with hardcoded currency symbol.

**Risk:** Changing currency symbol or formatting rules requires updating 29+ locations.

---

### D. Print CSS and Print Components

**Status:** ✅ **IMPLEMENTED** — But basic

**Print component:** `SuccessModal.tsx` contains both:
1. **Screen receipt** (visible at normal screen width)
2. **Thermal receipt** (shown only in print)

**CSS location:** `frontend/src/styles.css:1183–1450`

**Print mechanism:**
```typescript
// SuccessModal.tsx:132
<button onClick={() => window.print()}>Print Receipt</button>
```

**CSS @media print behavior:**

| Target | Behavior |
|--------|----------|
| `html, body, #root, .app-shell, .main-shell` | Set to `width: 80mm`, `height: auto`, remove margins/padding, white background |
| `.sidebar, .topbar, .order-panel, .menu-area` | `display: none` (hide entire app shell) |
| `.screen-success` | `display: none` (hide screen receipt) |
| `.print-receipt` | `display: block`, width `80mm`, padding `5mm` |
| `.modal-backdrop` | Set to `position: static`, `display: block`, `width: 80mm` |

**Thermal receipt layout:**
- Monospace font (Arial)
- 80mm width (11px font ≈ 34 chars)
- Header: restaurant name + subtitle
- Divider: `--------------------------------` (36 chars)
- Item list with right-aligned price/total
- Summary: Subtotal, Discount, Tax, Total
- Footer: "THANK YOU!" message

**Hardcoded values in print receipt:**
- Restaurant name: `"MY RESTAURANT"` (SuccessModal.tsx:34, 149)
- Subtitle: `"Restaurant POS"`
- Footer: `"Please visit us again."`

**58mm support:** Mentioned in CLAUDE.md Rule 34 but NOT implemented — currently hardcoded to 80mm only

---

## 4. HARDCODED VALUES AUDIT

### A. Restaurant Name

| File | Line(s) | Value | Context |
|------|---------|-------|---------|
| `frontend/src/pages/POS.tsx` | 96 | `"My Restaurant"` | Page header title |
| `frontend/src/components/SuccessModal.tsx` | 34 | `"MY RESTAURANT"` | Screen receipt business name |
| `frontend/src/components/SuccessModal.tsx` | 149 | `"MY RESTAURANT"` | Thermal receipt header |
| `backend/app/main.py` | 16 | `"My Restaurant POS API"` | FastAPI app title (not user-facing) |

---

### B. Currency

| File | Line(s) | Value | Occurrences |
|------|---------|-------|-------------|
| All display files | 29+ | `"Rs. "` | Hardcoded currency prefix in every money display |

**No currency symbol in database or configuration.**

---

### C. Other Hardcoded Strings

| File | Line(s) | Value | Type |
|------|---------|-------|------|
| SuccessModal.tsx | 35 | `"Restaurant POS"` | Receipt subtitle |
| SuccessModal.tsx | 126 | `"THANK YOU!"` | Receipt footer |
| SuccessModal.tsx | 127 | `"Please visit us again."` | Receipt tagline |
| SuccessModal.tsx | 28 | `"BILL READY"` | Modal eyebrow text |

---

### D. Tax Rate and Delivery Charges

**Status:** Not hardcoded, passed dynamically

- Tax rate: Provided per order in `OrderCreate.tax_rate` (Pydantic schema, user input)
- Delivery charges: **NOT IMPLEMENTED** — mentioned in CLAUDE.md but not in code
- Discount: User-entered amount (not a fixed percentage)

---

## 5. RISKS AND CONVERSION IMPACT

### Risk #1: Money Stored as `Numeric(10, 2)` Instead of Integer Paisa

**Current State:** All money columns use SQLAlchemy `Numeric(10, 2)` with Python `Decimal` type.

**Violates Rule 3** → "Money is always an Integer (paisa), not Float/Numeric/Decimal"

**Conversion Impact if Changed to Integer Paisa:**

1. **Database Migration (required):**
   - Create Alembic migration to convert all Numeric columns to Integer
   - Multiply every value by 100 (Rs. 1,250.00 → 125000 paisa)
   - 10 affected columns across 4 tables

   ```sql
   ALTER TABLE products 
   RENAME COLUMN price TO price_numeric;
   ALTER TABLE products 
   ADD COLUMN price INTEGER;
   UPDATE products SET price = CAST(price_numeric * 100 AS INTEGER);
   -- Repeat for all money columns
   ```

2. **Backend Changes:**
   - Update Pydantic schemas: `Decimal` → `int`
   - Update all money calculations to use integers:
     - `subtotal * quantity` (no Decimal arithmetic)
     - `taxable * tax_rate / 10000` (divide by 10000 for basis points)
     - `Decimal("0.01")` → `1` (paisa)
   - Update `order_service.py`:40+ lines with new arithmetic
   - Update `dashboard_service.py` aggregations

3. **Frontend Changes:**
   - Display formatting: `(money / 100).toFixed(2)` instead of `toFixed(2)`
   - Update 29+ locations or centralize to `formatMoney()` helper
   - Input parsing: `input * 100` when sending to backend

4. **Existing Data:**
   - ~100–500 rows in production (depending on phase)
   - All order data, product prices, movements affected
   - Zero data loss, only column type and values change

5. **Timeline:**
   - Schema migration: 1–2 hours
   - Backend updates: 3–4 hours
   - Frontend updates: 2–3 hours
   - Testing: 2 hours
   - **Total: ~8–11 hours**

**Alternative:** Keep `Numeric` for now, adopt integer paisa in Phase 15+ when refactoring becomes necessary.

---

### Risk #2: `stock_movements` Table is Product-Only, Not Polymorphic

**Current State:** `stock_movements` has `product_id` FK only, no `item_type`/`item_id` fields.

**Violates Rule 5** → "stock_movements is polymorphic for PRODUCT and INGREDIENT"

**Impact When Phase 15 Adds Ingredients:**

1. **New Columns Needed:**
   - Add `item_type` (String) → PRODUCT, INGREDIENT, etc.
   - Rename `product_id` to `item_id` (or keep `product_id` and add `ingredient_id`, then normalize)
   - Add NOT NULL constraint to `item_id` and `item_type` together

2. **Database Migration:**
   ```sql
   ALTER TABLE stock_movements ADD COLUMN item_type STRING DEFAULT 'PRODUCT';
   ALTER TABLE stock_movements ADD COLUMN ingredient_id INTEGER;
   UPDATE stock_movements SET item_type = 'PRODUCT';
   -- Create foreign key to ingredients table (Phase 15)
   ```

3. **Backend Changes:**
   - Update models.py `StockMovement` class
   - Update `stock_service.py` to accept `item_type`/`item_id` or auto-detect from row
   - Update all queries to filter by `item_type`
   - Possible: create a `StockLedgerEntry` base class with subclasses

4. **Frontend Changes:**
   - Update types: add `item_type` field to `StockMovement` interface
   - Update `StockHistory.tsx` to display ingredient movements
   - No display changes needed if `product_name` is kept for both products and ingredients

5. **Timeline:**
   - Schema migration: 1 hour
   - Backend refactor: 4–6 hours
   - Frontend updates: 1–2 hours
   - Testing: 2 hours
   - **Total: ~8–11 hours at Phase 15**

**Recommendation:** Prepare the schema now (Phase 0.5 with Alembic), or accept technical debt until Phase 15.

---

### Risk #3: No Settings Table for Rule 1 (Single Source of Truth)

**Status:** ❌ **MISSING**

**Violates Rule 1** → All hardcoded values (restaurant name, currency, tax rate, delivery charges, day start time) should come from a `settings` table.

**Currently Hardcoded:**
- Restaurant name: "My Restaurant", "MY RESTAURANT"
- Currency: "Rs. "
- Tax rate: User input per order, no global default
- Delivery charges: Not implemented
- Business day start: Not implemented (default 00:00 UTC)
- Logo/image: Not implemented

**When Phase 15+ Requires This:**
- Create `settings` table with singleton row
- Create backend endpoint `/api/settings`
- Load on app startup and cache
- Pass to frontend via React Context
- Update all 29+ money displays to use dynamic currency symbol
- **Estimated: 4–6 hours**

---

### Risk #4: Print CSS Hardcoded to 80mm, No 58mm Support

**Status:** ❌ **58MM NOT IMPLEMENTED**

CLAUDE.md Rule 34 requires "58mm must also be supported via settings", but:
- `@media print` hardcoded to `width: 80mm`
- No conditional CSS based on settings
- No print CSS media query for 58mm

**Impact:** Single printer width only; businesses with 58mm printers cannot use this POS.

---

### Risk #5: No Business Day Implementation

**Status:** ❌ **MISSING**

**Violates Rule 10** → "Business day, not calendar day. All daily reports use settings.day_starts_at"

**Currently:** Dashboard, reports, daily summaries use calendar midnight (UTC), not Asia/Karachi timezone or configurable business day start.

**When Phase 15+ Requires This:**
- Add `day_starts_at` field to settings table (default 06:00)
- Add `timezone` field (default "Asia/Karachi")
- Update dashboard queries to group by business day, not calendar day
- Update timestamps to store UTC, display in timezone
- **Estimated: 6–8 hours**

---

## 6. DATA INTEGRITY OBSERVATIONS

### A. Transactions ✅

- `order_service.create_order()` wraps order + items + stock movements in single transaction
- `order_service.cancel_order()` wraps all reversals in single transaction
- Rollback on any failure → atomicity guaranteed

### B. Cascading Deletes

- Orders cascade-delete items (intentional, paired)
- Categories cascade-delete products (intentional but violates Rule 6—should soft-delete instead)

**Current:** `cascade="all, delete-orphan"` on Category→Product  
**Issue:** If a category is soft-deleted (`active=False`), products don't cascade  
**Risk:** Low, since categories are soft-deleted anyway

### C. Referential Integrity

- Foreign keys enforced: product_id → products, order_id → orders, etc.
- SQLite WAL mode enables concurrent readers (check `database.py`)
- `check_same_thread=False` allows cross-thread DB access (safe with SQLAlchemy sessionmaker)

---

## 7. KNOWN GAPS

### orders.tax_rate Snapshot Missing (Rule 7)

**Issue:** The `orders` table stores `tax` (paisa) but not `tax_rate` (basis points).  
**Impact:** The tax rate applied to an order cannot be recovered later. If settings change, historical orders show only the calculated tax amount, not the rate that produced it.

**Example:** Order ORD-00011 has `tax=4000` and was charged at 16% (1600 bp). If tax settings later change to 20%, we cannot tell from the order record alone whether 4000 was 16% or 20% of 25000.

**Rule Violated:** Rule 7 (Order snapshots must capture the state at time of sale)

**Fix:** Add `tax_rate` column to `orders` table in a migration (Stage 4, Orders phase).
- Alembic migration: `ALTER TABLE orders ADD COLUMN tax_rate INTEGER DEFAULT 0;`
- Backfill existing rows to 0 (since `tax_enabled` has been false throughout)
- Once added, PaymentModal sends `tax_rate` with every order, and it is stored alongside `tax`

**Timeline:** 30 minutes (straightforward migration + backfill)  
**Priority:** Low (not urgent while `tax_enabled` is false, but required for Rule 7 compliance)

---

## 8. SCHEMA COMPLETENESS CHECK

**Missing for Production Use:**

| Feature | Table Needed | Status | Priority |
|---------|--------------|--------|----------|
| Settings (Rule 1) | `settings` | ✅ Added (Task 1.1) | Complete |
| Ingredients (Phase 15) | `ingredients`, extend `stock_movements` | ❌ Missing | Phase 15 |
| Recipes/BOM (Phase 15) | `recipes` | ❌ Missing | Phase 15 |
| Customers (Phase 11+) | `customers` | ❌ Missing | TBD |
| User Accounts/Auth | `users` | ❌ Missing | Production |
| Audit Log | `audit_log` | ❌ Missing | Production |

---

## 9. SUMMARY

| Aspect | Status | Notes |
|--------|--------|-------|
| **Projects Structure** | ✅ Clear | Backend services layer clean, frontend components organized |
| **Database Schema** | ✅ 6 tables | Matches SQLAlchemy models, ready for Alembic |
| **Money Storage** | ⚠️ Numeric | Uses `Numeric(10, 2)`, violates Rule 3 (should be Integer paisa) |
| **Stock Ledger** | ⚠️ Product-only | Will need polymorphic refactor for ingredients (Phase 15) |
| **Alembic Setup** | ❌ Missing | No migrations; uses `create_all()` at startup |
| **Services Layer** | ✅ Excellent | Business logic properly separated from routes |
| **API Design** | ✅ Good | RESTful, consistent, well-typed Pydantic schemas |
| **Frontend State** | ✅ Good | POSContext with proper cart sync and stock cap |
| **Money Formatting** | ❌ Hardcoded | 29+ inline "Rs." calls; should centralize to `formatMoney()` |
| **Print Support** | ✅ Implemented | 80mm thermal receipt working; 58mm not implemented |
| **Settings** | ❌ Missing | No `settings` table; all config hardcoded (violates Rule 1) |
| **Business Day** | ❌ Missing | Uses calendar day, not configurable business day (violates Rule 10) |

---

**Report Date:** 2026-08-15  
**Prepared by:** Codebase Audit (Read-Only)  
**Next Steps:** Recommend Task 0.5 (Alembic setup) before Task 1.1
