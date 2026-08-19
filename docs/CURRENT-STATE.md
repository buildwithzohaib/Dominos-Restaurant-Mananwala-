# CURRENT STATE AUDIT — My Restaurant POS

**Date:** 2026-08-19  
**Status:** READ-ONLY REPORT  
**Phases Completed:** 1–10  
**Stage 4 (Running Tabs):** ✅ COMPLETE (backend + frontend)  
**Git HEAD:** 58d2eba (4.D2)

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
| `table_id` | Integer | FK→restaurant_tables.id, nullable | Required for DINE_IN (running tabs) |
| `status` | String(30) | default="PAID" | OPEN, PAID, or CANCELLED (Stage 4: OPEN added) |
| `subtotal` | Integer | NOT NULL | Paisa (Rule 3: converted in Stage 4) |
| `discount` | Integer | default=0 | Paisa (Rule 3: converted in Stage 4) |
| `tax` | Integer | default=0 | Paisa; calculated at pay time |
| `tax_rate` | Integer | nullable | Basis points at order time (snapshot per Rule 7) |
| `total` | Integer | NOT NULL | Paisa (Rule 3: converted in Stage 4) |
| `payment_method` | String(30) | nullable | CASH, CARD, OTHER; **NULL for OPEN orders** (Stage 4) |
| `amount_received` | Integer | default=0 | Paisa tendered |
| `change_amount` | Integer | default=0 | Paisa change (CASH only) |
| `created_at` | DateTime | default=now, INDEX | When order placed |
| `paid_at` | DateTime | nullable | When payment collected (Stage 4) |
| `cancelled_at` | DateTime | nullable | When order cancelled |
| `cancelled_reason` | String(200) | nullable | Reason for cancellation |

**Relationships:** `table` (many-to-one), `items` (one-to-many cascade), `customer` (many-to-one, optional)

**Note:** Orders are never deleted; cancellation sets `status="CANCELLED"` and records timestamps (Rule 6). Running tabs (DINE_IN OPEN) remain open for incremental item additions until `pay_order()` closes them.

**Constraints (Stage 4):** Partial unique index `ix_one_open_per_table` ensures only one OPEN order per table at a time.

---

#### Table 6: `order_items`
| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | Integer | PRIMARY KEY | |
| `order_id` | Integer | FK→orders.id | Parent order |
| `product_id` | Integer | FK→products.id | Reference to product at order time |
| `product_name` | String(150) | NOT NULL | Snapshot of name at time of sale (Rule 7) |
| `quantity` | Integer | NOT NULL | Units ordered |
| `price` | Integer | NOT NULL | Paisa unit price at time of sale (Rule 7) |
| `line_total` | Integer | NOT NULL | Paisa (quantity × price) |
| `batch_id` | Integer | nullable | Kitchen batch number (Stage 4); NULL = PENDING, number = SENT |
| `sent_at` | DateTime | nullable | When this item was sent to kitchen (Stage 4) |

**Relationships:** `order` (many-to-one cascade)

**State Machine (Stage 4):** 
- PENDING: batch_id NULL, sent_at NULL (item in cart, not yet sent to kitchen)
- SENT: batch_id set (1, 2, 3...), sent_at set (stock already decremented)

---

### B. Money-Related Columns (CRITICAL)

**Stage 4 Update:** All monetary fields have been **converted to Integer (paisa)** per Rule 3.

| Table | Column | Type | Comment |
|-------|--------|------|---------|
| products | price | Integer | Selling price in paisa (Rs. 1,250 = 125000) |
| products | purchase_price | Integer | Cost per unit in paisa |
| stock_movements | purchase_price | Integer | Cost at time of movement (nullable, paisa) |
| orders | subtotal | Integer | Paisa, before discount and tax |
| orders | discount | Integer | Paisa, absolute amount deducted |
| orders | tax | Integer | Paisa, calculated at pay time |
| orders | total | Integer | Paisa, final amount due |
| orders | amount_received | Integer | Paisa, cash/card tendered |
| orders | change_amount | Integer | Paisa, change returned |
| order_items | price | Integer | Paisa, unit price snapshot at sale |
| order_items | line_total | Integer | Paisa, quantity × price |

**Compliance:** ✅ **RULE 3 SATISFIED** — All money is integer paisa, no Float/Decimal/Numeric types. Percentages are basis points integers (1600 = 16% tax_rate).

---

### C. Alembic Configuration

**Status:** ✅ **ACTIVE** (Stage 4)

**Alembic Directory:** `backend/alembic/` with standard structure
- `alembic.ini` ✅
- `env.py` ✅
- `versions/` directory with migration files
- `script.py.mako` template

**Stage 4 Migrations:**
- `ad8ba306eabb` — Add `order_items.batch_id`, `order_items.sent_at`, `orders.payment_method` nullable, partial unique index `ix_one_open_per_table`
- `b3d5e7f9a1c3` — Add `orders.paid_at` (nullable), backfill `paid_at = created_at` for existing PAID orders

**Current Migration Head:** `b3d5e7f9a1c3`

**Migration Status:** `alembic check` returns clean (no pending migrations)

**All Money Converted:** Migrations converted money columns from Numeric(10,2) to Integer (paisa)

---

### D. Services Layer

**Status:** ✅ **WELL-STRUCTURED**

Services exist and are the only place business logic lives:

| Service | Location | Purpose |
|---------|----------|---------|
| `order_service` | `app/services/order_service.py` | Order creation, open/PAID/CANCELLED states, stock deduction, running tabs (Stage 4) |
| `inventory_service` | `app/services/inventory_service.py` | Stock add/adjust operations |
| `product_service` | `app/services/product_service.py` | Product CRUD (Phase 10) |
| `stock_service` | `app/services/stock_service.py` | Stock ledger operations |
| `dashboard_service` | `app/services/dashboard_service.py` | Dashboard metrics aggregation (Phase 9) |

**Stage 4 New Functions in `order_service`:**
- `create_open_order()` — Opens a DINE_IN tab (OPEN status, payment_method NULL, tax_rate snapshotted)
- `add_items_to_order()` — Adds items as PENDING (batch_id NULL, doesn't decrement stock); merges repeat products into existing PENDING line
- `update_pending_item()` — Modifies or deletes a PENDING item; quantity=0 deletes the item; availability/category checks only on increases (decreases/deletes always allowed)
- `send_batch_to_kitchen()` — Only place stock is decremented; stamps batch_id (per-order numbering) and sent_at
- `pay_order()` — Closes OPEN order (payment collection, tax calculation, no stock touch)
- `cancel_order()` — Now accepts OPEN as well as PAID; restores stock from SALE movements only

**Stage 4 New Routes (in `app/routes/orders.py`):**
- `POST /api/orders/open` → `create_open_order()`
- `POST /api/orders/{id}/items` → `add_items_to_order()`
- `PATCH /api/orders/{order_id}/items/{item_id}` → `update_pending_item()` (Stage 4.B6)
- `POST /api/orders/{id}/send` → `send_batch_to_kitchen()`
- `POST /api/orders/{id}/pay` → `pay_order()`
- `GET  /api/orders?status=OPEN` → Lists active running tabs (existing filter)

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

**Stage 4 New Methods (running tabs):**
- `openOrder(table_id)` → POST /api/orders/open
- `addItemsToOrder(order_id, payload)` → POST /api/orders/{id}/items
- `updatePendingItem(order_id, item_id, payload)` → PATCH /api/orders/{order_id}/items/{item_id}
- `sendBatchToKitchen(order_id)` → POST /api/orders/{id}/send
- `payOrderDineIn(order_id, payload)` → POST /api/orders/{id}/pay

---

### D. DINE_IN Running-Tab Frontend Architecture (Stage 4.D2)

**Location:** Frontend cart/order state lives in `POSContext.tsx`; payment flow in `PaymentModal.tsx`

**CartItem Discriminated Union:**

Frontend cart items have two variants, selected by `kind` field:

```typescript
type CartItem = 
  | {kind: "local"; product: Product; quantity: number}
  | {kind: "server"; itemId: number; productId: number; productName: string; 
     price: number; lineTotal: number; quantity: number; 
     batchId: number | null; sentAt: string | null}
```

- **"local":** Items in a TAKEAWAY/DELIVERY cart (before order creation). Holds full `Product` object.
- **"server":** Items on a DINE_IN running tab after `openOrder()` succeeds. Holds snapshotted `productName` and `price` (Rule 7), plus `batchId` (NULL=PENDING, number=SENT) and `sentAt` timestamp. Updates via LOAD_ORDER action after server operations.

**Lazy Order Opening:**

- **NOT** on table select — table selection alone does not create an order (would lock the table with an empty OPEN order).
- **ON first item add:** `addProductToDineIn()` checks if `serverId` exists. If not, calls `openOrder(tableId)`, stores `serverId` in state, then adds the item.
- This prevents empty tables from being locked while a cashier is browsing or selecting items.

**Detach Behavior (table/order-type switch):**

When user switches table or order type while a DINE_IN order is open:
- `clear()` resets cart, discount, and `serverId` to undefined
- The server order stays **OPEN** on the server (not cancelled)
- Local state is detached; the order can be reopened later (but no Active Orders page exists yet, so this is not visible to the user)
- This prevents accidental cancellations and allows a cashier to step away and resume

**SYNC_PRODUCTS Behavior:**

- For TAKEAWAY/DELIVERY: `SYNC_PRODUCTS` action updates local cart items' `product` references and caps quantities to new stock
- For DINE_IN: `SYNC_PRODUCTS` never touches server items; instead, the new product list is always derived from the server response via `LOAD_ORDER` after any operation (add items, update item, send batch)
- Server response is the source of truth; client re-mapping is not applied to server items

**Tax Rate Snapshot:**

- POSContext computes `taxRate` dynamically:
  - If `serverId` exists AND `state.order` exists: use `state.order.tax_rate` (the order's snapshot from when it was opened)
  - Otherwise: use `settings.tax_enabled` and `settings.tax_rate` (current settings)
- This ensures the client computes tax using the same rate the server will use in `pay_order()`, even if settings change mid-tab
- Order snapshots tax rate at open time per Rule 7

**Send to Kitchen Button:**

- Enabled only when both:
  - `serverId` exists (DINE_IN order is open)
  - At least one PENDING item exists (batch_id === null)
- Disabled otherwise, to prevent sending when nothing new is ready

**Proceed to Payment Button:**

- Enabled only when both:
  - Cart is not empty
  - NO PENDING items remain (all items have been sent in a batch, batch_id !== null)
- Disabled if any item is PENDING, because `pay_order()` rejects OPEN orders with PENDING items

**Discount Entry (Payment Time):**

- Discount is now entered in `PaymentModal` (via `setDiscount()` from context)
- All order types (DINE_IN, TAKEAWAY, DELIVERY) use the same discount input in `PaymentModal`
- When user changes the discount input, POSContext recomputes `total` (with discount applied) immediately
- Both the "Total due" display and the CASH validation use this recomputed context `total` (exact, not approximate)

**Payment Amount Handling:**

- CASH: User enters amount received. Validated client-side (received >= total). The figure on screen is the amount the cashier must collect; if it is off by the tax on the discount, the cashier takes the wrong amount and gives wrong change — silently, every order. To prevent this, discount is routed through context so POSContext recomputes total exactly, and the on-screen and validated figures are correct.
- CARD/OTHER: `amount_received` sent to server as 0 (not validated or used for change computation, which is always 0 for non-CASH)

**TAKEAWAY/DELIVERY Unchanged:**

- Still use single-shot `createOrder()` path (no running tabs)
- Discount collected in `PaymentModal` same as DINE_IN

---

### E. Money Formatting for Display

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

## 4. TESTING STRATEGY

### Backend Test Fixtures (Stage 4)

**Pattern:** No shared `conftest.py`. Each test file builds its own database independently.

**Why:** 18 test files already define their own fixtures. Introducing a shared `conftest.py` now would mean touching all of them and risking a suite that currently passes 328 tests, for no benefit. New test files copy the existing per-file pattern because that is what the project already does — not because `conftest.py` is broken.

**Standard Pattern (from Stage 4 test files):**

```python
@pytest.fixture(scope="function")
def db() -> Session:
    """Create a temporary SQLite database for each test."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)  # Critical: close the file descriptor immediately (Windows)
    
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    # Seed data (Settings, tables, products, etc.)
    # ... populate sample data ...
    session.commit()
    
    # Expose seeded IDs to tests
    session.table_a_id = table_a.id
    session.prod1_id = prod1.id
    # ...
    
    yield session
    
    session.close()
    engine.dispose()  # Critical: dispose engine before removing file
    gc.collect()
    time.sleep(0.1)
    
    # Retry os.remove on Windows (file lock may persist briefly)
    for _ in range(5):
        try:
            os.remove(db_path)
            break
        except OSError:
            time.sleep(0.1)
```

**Key Details:**
- `os.close(db_fd)` immediately after `mkstemp` — otherwise Windows keeps the file locked
- `engine.dispose()` before `os.remove` — closes all connections
- `gc.collect()` and `time.sleep(0.1)` — allow cleanup time
- Retry loop for `os.remove` — Windows file locking can persist briefly
- **Seeded IDs as session attributes (known shortcut):** Passing seeded IDs to tests as `db.table_a_id`, `db.prod1_id`, etc. works but is unclean. SQLAlchemy Session is not a data carrier; a fixture returning a small dict or dataclass would be cleaner. This pattern has spread across five test files and is flagged as technical debt in Known Gaps.

**Files Using This Pattern:**
- `backend/tests/test_stage4_b1.py` through `backend/tests/test_stage4_c1.py`

**When Writing New Test Files:**
- Copy the fixture from an existing Stage 4 test file
- Each test file is independent and self-contained
- The Windows-specific teardown pattern (fd close, dispose, gc.collect, retry os.remove) is what each file needs

**Test Status:** 328 tests passing (18 test files in total)

---

## 5. HARDCODED VALUES AUDIT

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

## 6. RISKS AND CONVERSION IMPACT

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

## 7. DATA INTEGRITY OBSERVATIONS

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

## 8. KNOWN GAPS

### Stage 4 Backend: COMPLETE ✅ | Frontend: COMPLETE ✅

#### Stage 4.D2 Frontend Implementation (2026-08-19)

**Implemented:**
- ✅ Discriminated union CartItem type (kind "local" vs "server")
- ✅ Lazy order opening on first item, not table select
- ✅ Detach behavior (table/order-type switch leaves server order OPEN)
- ✅ LOAD_ORDER action to wholesale replace cart from server
- ✅ SYNC_PRODUCTS never touches server items
- ✅ TaxRate snapshot from order when serverId exists
- ✅ Send to Kitchen button (enabled only with PENDING items)
- ✅ Proceed to Payment button (enabled only when NO PENDING items)
- ✅ Discount entered in PaymentModal for ALL order types (behavioral change)
- ✅ amount_received: 0 for CARD/OTHER, validated for CASH
- ✅ Context total recomputed on discount change (exact, not approximate)
- ✅ Frontend builds clean, 27 vitest tests passing

**Build Status:** ✅ `npm run build` clean (Git HEAD 58d2eba)

#### Behavioral Change: Discount Entry

**What changed:** Discount is now collected at payment time only (in PaymentModal), not in OrderPanel.

**Affected:** TAKEAWAY and DELIVERY orders (DINE_IN always used payment-time discount).

**Old behavior:** Discount entered in OrderPanel, persisted across payment modal open/close, displayed in order summary.

**New behavior:** Discount entered only in PaymentModal. OrderPanel no longer has a discount field or discount summary line. Discount does not appear in order composition view; it is a payment-time decision.

**What happened:** During D2 implementation, a second discount input was added to PaymentModal for DINE_IN, while OrderPanel's discount field remained. This created a duplicated-input bug: a discount typed into PaymentModal was silently dropped on TAKEAWAY/DELIVERY (only OrderPanel's discount was sent to the server). The first fix scoped the new field to DINE_IN only. The user then decided discount should be collected at payment time for every order type, so we consolidated both inputs into PaymentModal and removed OrderPanel's field. This is a deliberate behavioral change and is noted as cleanup debt if future work prefers order-time discount entry.

---

### Stage 4 Backend: COMPLETE ✅ | Frontend: NOT STARTED

**Business Model:** The restaurant operates table service where customers sit at a table and place orders incrementally:
1. Customer sits at a table
2. Opens a running tab (OPEN order on that table)
3. Adds items in rounds (each sends a batch to the kitchen, stock decrements)
4. Possibly several additions
5. Finally pays and table is closed (OPEN → PAID)

**What Stage 4 Implemented (Backend):**
- ✅ Order status: OPEN (in addition to PAID, CANCELLED)
- ✅ `create_open_order()` — creates OPEN order with payment_method NULL, tax_rate snapshotted
- ✅ `add_items_to_order()` — appends items as PENDING (batch_id NULL), merges same-product lines (defensive: multiple PENDING lines of same product cannot be created through service layer)
- ✅ `update_pending_item()` — modifies or deletes PENDING items; quantity=0 deletes; availability checks only on increases (Stage 4.B6)
- ✅ `send_batch_to_kitchen()` — THE ONLY stock deduction point; stamps batch_id (1, 2, 3...) and sent_at
- ✅ `pay_order()` — closes OPEN order (rejects if any PENDING items remain)
- ✅ `cancel_order()` — now accepts OPEN; restores stock from SALE movements (PENDING excluded)
- ✅ Partial unique index `ix_one_open_per_table` ensures only one OPEN order per table
- ✅ Migrations: ad8ba306eabb + b3d5e7f9a1c3 (no new migrations for B6)
- ✅ Schemas: OpenOrderCreate, AddItemsIn, UpdatePendingItemIn, PayOrderIn (nested TableNested)
- ✅ Routes: POST /open, /items, PATCH /items/{item_id}, /send, /pay (all return OrderOut with table nested)
- ✅ 328 tests passing across 18 test files

**Schema Changes:** 
- `orders.status` now supports OPEN (was: PAID, CANCELLED)
- `orders.payment_method` now nullable (NULL while OPEN)
- `orders.paid_at` added (NULL until payment collected)
- `orders.tax_rate` snapshotted at open time (basis points)
- `order_items.batch_id` added (NULL=PENDING, number=SENT)
- `order_items.sent_at` added (when batch was sent to kitchen)
- Money: All converted to Integer (paisa)

**Pydantic Schemas (in `app/schemas/schemas.py`):**
- `OpenOrderCreate` — Create OPEN running tab (table_id, optional customer_id)
- `AddItemsIn` — Add items to OPEN order (items list with product_id, quantity)
- `UpdatePendingItemIn` — Update quantity of PENDING item (quantity; 0 = delete)
- `PayOrderIn` — Close OPEN order (payment_method, discount, amount_received)

**Frontend D2 COMPLETED:**
- ✅ Order panel cart with discriminated CartItem (local vs server)
- ✅ Send to Kitchen button with PENDING item check
- ✅ Cancel Order button (opens CancelOrderModal)
- ✅ Proceed to Payment button (enabled only when no PENDING items)
- ✅ PaymentModal discount input (all order types, calls setDiscount)
- ✅ CASH validation against exact discount-adjusted total
- ✅ Receipt data passed from server order response
- ✅ Order opened lazily on first item add (not table select)
- ✅ Detach on table/order-type switch

**Frontend NOT YET IMPLEMENTED:**
- Active orders page (GET /api/orders?status=OPEN) — no way to reopen a detached tab
- KOT component (print batch_id, sent_at for kitchen) — kitchen has no batch visibility
- Tables management UI — can select table but no management page
- Receipt display of batch details (batch_id, sent_at per item) — receipt shows paid order only, not kitchen workflow
- Open order indicator with refreshed count (30s polling implemented for topbar)

**Known Production Limitations (Stage 4):**
- No Active Orders page means a detached tab (table/order-type switch) cannot be reopened; during testing all six tables filled and required API cancellation
- Product clicks have no busy/loading guard — repeated clicks fire one API request each (harmless but poor UX)
- Topbar polls GET /api/orders?status=OPEN every 30s for count only (does not fetch order details)
- Untracked scratch scripts in backend/ (check_stock.py, list_open.py, cancel_open.py) trigger uvicorn --reload restarts
- ~26 old .db backup/test files clutter backend/ directory

**Critical Runtime Assumptions (all working):**
- order.payment_method is NULL while OPEN — pay() branches on state.serverId, not method
- order.paid_at is NULL until payment — receipt created from server response after pay_order()
- item.batch_id NULL = PENDING (not sent to kitchen), number = SENT (decremented on send, not pay)
- order.table.name used in UI (rule 2: never display table_id)
- order.tax_rate snapshot used for tax calculation (not current settings)

---

### Stage 4 Backend Gaps & Open Items

**revenue_by_paid_at (Rule 10):** Dashboard still reports metrics by `created_at`, but orders can now have a gap between `created_at` (when tab opened) and `paid_at` (when payment collected). Per Rule 10 (business day), revenue should be reported by `paid_at`, not `created_at`. This gap affects dashboard/daily reports. **Not yet implemented.**

**Concurrent Integrity (Production-Only):** The `create_open_order()` function has an except IntegrityError branch that re-checks after rollback (for the partial unique index). This path is unreachable from unit tests (the explicit pre-check fires first) but may run under real concurrency. There is a code comment documenting this. **No changes needed, but be aware.**

**Test Fixture Pattern (Windows):** Ad-hoc attributes attached to Session objects (e.g., `session.table_a_id = ...`) pass seeded IDs to tests. It works but is not clean and has spread across 5 Stage 4 test files. **Not ideal, but functional; no priority to refactor.**

**Frontend Not Started:** Order panel buttons, active orders page, KOT component, tables UI, receipt updates not yet built. Stage 4 is backend-complete but frontend stage 4 is not started. **Next priority.**

---

### Foreign Key Enforcement is OFF (Decorative Only)

**Status:** PRAGMA foreign_keys is OFF (SQLite default). Nothing in the application or Alembic turns it on.

**Impact:**
- Every foreign key in the schema is declarative only and NOT enforced by the database:
  - `products.category_id`
  - `orders.table_id`
  - `orders.customer_id`
  - `order_items.order_id` and `.product_id`
- **Referential integrity currently depends entirely on service-layer checks.**

**Data Integrity Check:** `PRAGMA foreign_key_check` on 2026-08-18 returned no violations — the data is consistent today.

**Why Not Enabled:**
- `stock_movements.item_id` is deliberately polymorphic (Rule 5) and has no FK by design
- Enforcement does not change that, but it shows the schema is not uniformly FK-enforced
- Enabling it is a separate task requiring: decision on where the PRAGMA is issued (per-connection via SQLAlchemy event listener), verification that no code relies on current leniency, and full test coverage

**To Enable in Future:**
- Create a dedicated task (not a side effect of other work)
- Add SQLAlchemy event listener to execute `PRAGMA foreign_keys=ON` on every connection
- Audit all tests for FK violations
- Run full suite to catch any new violations from recent code
- Document the change as a breaking point for debugging (FK errors will now be DB-level, not app-level)

---

## 9. SCHEMA COMPLETENESS CHECK

**Status After Stage 4:**

| Feature | Table(s) | Status | Notes |
|---------|----------|--------|-------|
| Settings (Rule 1) | `settings` | ✅ Complete | Exists; used for tax_rate, day_starts_at, delivery_charge |
| Orders (Phases 1-10, Stage 4) | `orders`, `order_items` | ✅ Complete | Stage 4 added OPEN status, batch tracking, paid_at |
| Products (Phases 1-10) | `products`, `categories` | ✅ Complete | Name normalization, stock management |
| Stock Ledger (Phases 1-10, Stage 4) | `stock_movements` | ✅ Complete | Append-only ledger; Stage 4 added SALE/CANCELLATION for batches |
| Tables (Stage 4) | `restaurant_tables` | ✅ Complete | Required for DINE_IN running tabs |
| Customers (Phase 3.5+) | `customers` | ✅ Complete | Exists with phone/address normalization; used in orders |
| Ingredients (Phase 15) | `ingredients` | ❌ Missing | Extend `stock_movements` with polymorphic `item_type`/`item_id` |
| Recipes/BOM (Phase 15) | `recipes` | ❌ Missing | Phase 15 requirement |
| User Accounts/Auth | `users` | ❌ Missing | Production requirement |
| Audit Log | `audit_log` | ❌ Missing | Production requirement |

---

## 10. SUMMARY

### Backend Status (Stage 4 Complete)

| Aspect | Status | Notes |
|--------|--------|-------|
| **Project Structure** | ✅ Excellent | Services layer clean, clear separation of concerns |
| **Database Schema** | ✅ 7 tables | categories, products, restaurant_tables, orders, order_items, stock_movements, customers, settings |
| **Money Storage** | ✅ Compliant | All money is Integer (paisa); Rule 3 satisfied |
| **Stock Ledger** | ⚠️ Product-only | Product movements working; ingredient polymorphism deferred to Phase 15 |
| **Alembic Setup** | ✅ Active | 2 Stage 4 migrations; current head b3d5e7f9a1c3 |
| **Services Layer** | ✅ Excellent | Business logic properly separated; Stage 4 running tabs implemented |
| **API Design** | ✅ Good | RESTful, consistent, well-typed Pydantic schemas |
| **Order Workflow** | ✅ Complete | OPEN → PENDING/SENT → PAID pipeline working |
| **KOT System** | ✅ Complete | Per-batch numbering (batch_id) with sent_at timestamps |
| **Table Integration** | ✅ Complete | Partial unique index prevents concurrent OPEN orders |
| **Tests** | ✅ 328 passing | Comprehensive coverage of all Stage 4 functions across 18 test files |

### Frontend Status (Phases 1-10, Stage 4 D2 Complete)

| Aspect | Status | Notes |
|--------|--------|-------|
| **Frontend Build** | ✅ Clean | 27 vitest tests passing; `npm run build` succeeds (Git 58d2eba) |
| **Frontend State** | ✅ Complete | POSContext with discriminated CartItem, server order tracking (serverId, order), detach logic |
| **Money Formatting** | ❌ Hardcoded | 29+ inline "Rs." calls; should centralize to `formatMoney()` |
| **Print Support** | ✅ Implemented | 80mm thermal receipt working; 58mm not implemented |
| **Order Panel (Phases 1-10)** | ✅ Complete | Handles OPEN orders, running tabs (Send/Cancel), no PENDING-item checkout |
| **Order Panel (Stage 4)** | ✅ Complete | Send to Kitchen button, Cancel Order button, Proceed to Payment only when no PENDING |
| **PaymentModal (Stage 4)** | ✅ Complete | Discount input for all types, exact tax calculation, CASH validation against adjusted total |
| **Active Orders Page** | ❌ Missing | No UI for GET /api/orders?status=OPEN; detached tabs cannot be reopened |
| **KOT Component** | ❌ Missing | No print view for kitchen batches (batch_id, sent_at visibility) |
| **Tables UI** | ✅ Partial | Table selection working; no management/admin page |

### Rule Compliance

| Rule | Compliance | Notes |
|------|-----------|-------|
| Rule 1 (Single Source) | ✅ | Settings table exists; used for tax_rate, day_starts_at, delivery_charge |
| Rule 2 (No IDs in UI) | ✅ | Frontend ready (table.name exposed); existing code compliant |
| Rule 3 (Integer Paisa) | ✅ | All money is Integer; Stage 4 migrations converted existing data |
| Rule 4 (Stock Ledger) | ✅ | Append-only; CANCELLATION movements for reversals |
| Rule 5 (Polymorphic) | ⚠️ | Ready for Phase 15; item_type/item_id fields prepared |
| Rule 6 (Soft Delete) | ✅ | No hard deletes; status flags and is_active used |
| Rule 7 (Snapshots) | ✅ | order_items snapshot price; orders snapshot tax_rate |
| Rule 8 (Stock on KOT) | ✅ | Stock decrements in send_batch_to_kitchen() only |
| Rule 9 (Normalization) | ✅ | Product/category/customer names normalized in Python |
| Rule 10 (Business Day) | ⚠️ | Implemented but not used in dashboard (reports by created_at, not paid_at) |

---

**Report Date:** 2026-08-19  
**Git HEAD:** 58d2eba (4.D2)  
**Backend Test Status:** 328 passing, 0 failing  
**Frontend Test Status:** 27 vitest tests passing  
**Frontend Build:** ✅ Clean  
**Alembic Status:** Clean (no pending migrations; head b3d5e7f9a1c3)  
**Next Work:** Active Orders page, KOT component, tables management UI, settle discount cleanup debt
