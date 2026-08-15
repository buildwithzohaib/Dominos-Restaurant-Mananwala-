# Money Conversion Task (0.6) — Additions 1-4 Summary

**Date:** 2026-08-15  
**Task:** Convert money from Numeric to Integer paisa with critical additions

---

## ADDITION 1: Tax Rate Input Conversion (16% → 1600 basis points)

### PROBLEM
UI user enters 16 (percent), but POSContext uses it directly as basis points.
Result: tax is 100x too small (Rs. 1.44 instead of Rs. 144).

### LOCATIONS FOUND

**Frontend inputs:**
- `OrderPanel.tsx:115` — `<input type="number" value={state.taxRate} ...>` (user enters percent)

**Frontend state:**
- `POSContext.tsx:5` — `initialState.taxRate = 0` (should be 0 basis points)
- `POSContext.tsx:18` — `case "TAX": return {...s, taxRate: Math.max(0, a.value)}` (stores input directly)
- `POSContext.tsx:51` — `tax = (subtotal - discount) * state.taxRate / 100` (current calc, wrong)

**Frontend API call:**
- `PaymentModal.tsx:76` — `tax_rate: Number(state.taxRate)` (sends to backend)

**Backend schema:**
- `schemas.py:45` — `tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)` (expects 0-100)

**Backend service:**
- `order_service.py:57` — `tax = money(taxable * payload.tax_rate / Decimal("100"))` (expects 0-100)

**Tests (all use 0 for tax_rate, so don't catch the bug):**
- `test_phase8.py`, `test_phase8_v2.py`, `test_phase9.py`, `test_phase9_simple.py` (multiple lines)

### SOLUTION

**Decision:** UI displays percent (0-100), but converts to basis points (0-10000) at the input boundary.

**Conversion formula:** `basisPoints = Math.round(percent * 100)`

**Implementation points:**

1. **OrderPanel.tsx** — Add onChange handler to convert input:
   ```typescript
   const handleTaxRateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
     const percent = parseFloat(e.currentTarget.value) || 0;
     pos.setTaxRate(Math.round(percent * 100));  // Store as basis points
   };
   ```

2. **POSContext.tsx** — Update reducer and initial state:
   ```typescript
   // taxRate stored in basis points (0-10000)
   const initialState = {..., taxRate: 0};  // 0 basis points
   ```

3. **POSContext.tsx** — Update tax calculation:
   ```typescript
   const tax = Math.floor((taxable * state.taxRate + 5000) / 10000);
   ```

4. **PaymentModal.tsx** — Tax rate already sent as-is (now in basis points)

5. **Schemas** — Change tax_rate to basis points:
   ```python
   tax_rate: int = Field(default=0, ge=0, le=10000)  # Basis points
   ```

6. **order_service.py** — Update calculation:
   ```python
   tax = (taxable * payload.tax_rate + 5000) // 10000  # Half-up rounding
   ```

### TEST CASE

**Input:** User enters 16 in tax rate field  
**POSContext state:** `taxRate: 1600`  
**API request body:**
```json
{
  "tax_rate": 1600,
  "order_type": "TAKEAWAY",
  ...
}
```
**Expected tax on Rs. 900:**
```
(90000 * 1600 + 5000) // 10000 = 14400 paisa (Rs. 144) ✅
```

---

## ADDITION 2: Money Input Boundaries (All Input Locations)

### LOCATIONS FOUND

**Product create/edit (price, purchase_price):**
- `AddProductModal.tsx:56` — price (type="number")
- `AddProductModal.tsx:89` — purchase_price (type="number")
- `EditProductModal.tsx:57` — price (type="number")
- `EditProductModal.tsx:88` — purchase_price (type="number")

**Stock management (purchase_price, quantity):**
- `AddStockModal.tsx:99` — purchase_price (type="number")
- `AddStockModal.tsx:111` — quantity adjustment (paisa - no conversion needed)
- `EditInventoryModal.tsx:104` — purchase_price (type="number")
- `StockAdjustmentModal.tsx:97` — quantity_change (integer - no conversion needed)

**Inventory edit (purchase_price):**
- `EditInventoryModal.tsx:89` — purchase_price (type="number")
- `EditInventoryModal.tsx:115` — price (type="number")

**Order flow (discount, amount received):**
- `OrderPanel.tsx:100` — discount (type="number")
- `OrderPanel.tsx:113` — taxRate (type="number") [already handled in ADDITION 1]
- `PaymentModal.tsx:199` — amount_received (type="number")

### INPUT/OUTPUT PATTERN

**INPUT (user types decimal rupees):**
```typescript
// User types: 450.50
// We send to backend: 45050 (paisa)
const handlePriceChange = (e) => {
  const rupees = parseFloat(e.target.value) || 0;
  setPrice(rupeesToPaisa(rupees));  // Convert to paisa
};
```

**DISPLAY (load existing amount):**
```typescript
// Database has: 45050 (paisa)
// We show to user: "450.50" (rupees)
// WRONG: value={product.price.toFixed(2)}
// CORRECT: value={(product.price / 100).toFixed(2)}
```

### CHANGES NEEDED (11 input locations)

| File | Line(s) | Field | Change |
|------|---------|-------|--------|
| AddProductModal.tsx | 56, 89 | price, purchase_price | onChange: `setPrice(rupeesToPaisa(...))` |
| EditProductModal.tsx | 57, 88 | price, purchase_price | Same |
| AddStockModal.tsx | 99, 111 | purchase_price, quantity | purchase_price: convert; quantity: none |
| EditInventoryModal.tsx | 89, 104, 115 | purchase_price, purchase_price, price | All: convert to paisa |
| OrderPanel.tsx | 100 | discount | onChange: `setDiscount(rupeesToPaisa(...))` |
| PaymentModal.tsx | 199 | amount_received | onChange: `setAmountReceived(rupeesToPaisa(...))` |

---

## ADDITION 3: Seed Data and Test Fixtures

### seed.py Hardcoded Money Values

**Lines 20-61 (DEFAULT_PRODUCTS):**
```python
# BEFORE (in rupees, will become 0.01x after migration)
"price": "250",        # Will be stored as 250 paisa (Rs. 2.50)
"purchase_price": "150",

# AFTER (multiply by 100 to stay in correct paisa range)
"price": "25000",      # Now 25000 paisa (Rs. 250) ✓
"purchase_price": "15000",
```

**All product prices to multiply by 100:**
- Line 25: "250" → "25000" (Chicken Nuggets)
- Line 29: "150" → "15000"
- Line 35: "150" → "15000" (Regular Fries)
- Line 39: "90" → "9000"
- Line 45: "650" → "65000" (Zinger + Fries + Drink)
- Line 49: "430" → "43000"
- Line 55: "80" → "8000" (Pepsi)
- Line 59: "60" → "6000"

**Also in seed.py code:**
- Line 149: `Decimal(product_info["price"])` — will receive integer string, works
- Line 153: `Decimal(product_info["purchase_price"])` — same

**File changes:** `backend/app/seed.py` (8 values × 2 = 16 updates)

### Test Files with Hardcoded Money

**Status:** All test_phase*.py files use `tax_rate=Decimal("0")`, so they're safe.

**Check:** `test_phase8.py`, `test_phase8_v2.py`, `test_phase9.py`, `test_phase9_simple.py`
- They create OrderCreate payloads with Decimal money values
- After backend schema changes to `int`, these will FAIL
- Need to convert test fixture money to paisa:
  - Before: `subtotal=Decimal("950")` (rupees)
  - After: `subtotal=95000` (paisa)

---

## ADDITION 4: Verification Mismatch Interpretation

### How Backfill and Verify Work Independently

**Backfill (`backfill_paisa.py`):**
```sql
UPDATE products SET price_paisa = CAST(ROUND(price * 100) AS INTEGER)
```
- Uses SQL ROUND (half-away-from-zero)
- Example: 450.555 * 100 = 45055.5 → ROUND → 45056

**Verify (`verify_paisa_conversion.py`):**
```python
expected = int(Decimal(str(old_val)) * 100)
```
- Uses Python int() truncation after Decimal multiplication
- Example: Decimal("450.555") * 100 = Decimal("45055.5") → int() → 45055

### When They Disagree

**Normal data (exactly 2 decimal places):** Always agree
```
450.50 * 100 = 45050.00
ROUND(45050.00) = 45050  ✓
int(45050.00) = 45050    ✓
```

**Exceptional data (>2 decimal places in storage):** Disagree
```
450.555 * 100 = 45055.5
ROUND(45055.5) = 45056  (SQL rounds up)
int(45055.5) = 45055    (Python truncates)
```

### What to Do If Mismatch Occurs

**NEVER:**
- Change the verifier to match backfill (defeats the purpose)
- Round away the discrepancy (hides data quality issues)

**DO:**
- Print the raw stored value for that row
- Show it to the user
- Investigate: why does this Numeric column hold >2 decimal places?
- Example output:
  ```
  ❌ Row id=42, products.price:
      old=450.555        (unusual! exceeds Numeric(10,2) precision)
      backfill=45056     (SQL ROUND)
      verify=45055       (Python truncate)
      difference=-1 paisa
  ```

---

## EXECUTION CHECKLIST

### Before Step 1
- [ ] Read and understand all 4 additions
- [ ] Verify tax_rate conversion logic
- [ ] List all 11 money input locations
- [ ] Identify seed.py and test file changes needed
- [ ] Understand mismatch handling

### Step 1-4 (No Code Changes)
- [ ] Backup and baseline
- [ ] Migration A
- [ ] Backfill
- [ ] Verify (STOP HERE — show output before Migration B)

### Step 5+ (With Additions)
- [ ] Fix tax_rate conversion in OrderPanel + POSContext + schemas + services
- [ ] Add rupeesToPaisa() conversion to 11 input locations
- [ ] Update seed.py (8 product prices × 100)
- [ ] Update test_phase*.py fixtures (convert to paisa)
- [ ] Run `npm run test` and `pytest` — must both pass
- [ ] End-to-end test with tax_rate validation

---

**Status:** Ready for implementation steps.  
**STOP after Step 4** and show verification output before proceeding to Step 5 (Migration B).
