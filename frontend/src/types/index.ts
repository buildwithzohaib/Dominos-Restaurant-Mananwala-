export type OrderType = "DINE_IN" | "TAKEAWAY" | "DELIVERY";
export type PaymentMethod = "CASH" | "CARD" | "OTHER";
export type StockStatus = "IN_STOCK" | "LOW_STOCK" | "OUT_OF_STOCK";
// Settings (Task 1.1) — single immutable row with restaurant configuration
export interface Settings { id:number; restaurant_name:string; restaurant_address:string; restaurant_phone:string; currency_symbol:string; tax_rate:number; /* basis points */ tax_enabled:boolean; delivery_charge:number; /* paisa */ day_starts_at:string; /* HH:MM format */ receipt_footer_text:string; theme:string; /* hidden theme choice */ created_at:string; updated_at:string; }
export interface SettingsUpdate { restaurant_name?:string; restaurant_address?:string; restaurant_phone?:string; currency_symbol?:string; tax_rate?:number; /* basis points */ tax_enabled?:boolean; delivery_charge?:number; /* paisa */ day_starts_at?:string; receipt_footer_text?:string; theme?:string; }
export interface Category { id:number; name_display:string; active:boolean; }
export interface CategoryInfo { id:number; name_display:string; active:boolean; }
// Inventory fields (Phase 3) live on the same Product row the POS/cart/receipt already
// read — sku/min_stock/unit/purchase_price/stock_status/updated_at are additive, and
// price/stock remain the single authoritative selling-price/current-stock values.
export interface Product { id:number; category_id:number; category:CategoryInfo; name_display:string; price:number; /* paisa */ stock:number; image?:string|null; image_hash?:string|null; available:boolean; status:string; sku:string; min_stock:number; unit:string; purchase_price:number; /* paisa */ stock_status:StockStatus; updated_at:string; }
export interface InventoryUpdateInput { name?:string; sku?:string; min_stock?:number; unit?:string; purchase_price?:number; /* paisa */ price?:number; /* paisa */ }
// Stock operations (Phase 4–8) — every change to Product.stock writes one of
// these ledger rows in the same backend transaction; Product.stock stays the only
// authoritative current-stock value, this just explains its history.
export type MovementType = "PURCHASE" | "ADJUSTMENT" | "SALE" | "CANCELLATION";
export type AdjustmentReason = "DAMAGED" | "EXPIRED" | "LOST" | "MANUAL_CORRECTION" | "OTHER";
export interface StockPurchaseInput { quantity:number; purchase_price?:number; /* paisa */ supplier:string; }
export interface StockAdjustmentInput { quantity_change:number; reason:AdjustmentReason; note?:string; }
export interface StockMovement { id:number; item_type:string; /* 'PRODUCT' | 'INGREDIENT' */ item_id:number; item_name:string; movement_type:MovementType; quantity_change:number; reason:string; supplier?:string|null; purchase_price?:number|null; /* paisa */ stock_before:number; stock_after:number; reference?:string|null; created_at:string; }
// Stock Reconciliation (Stage 5)
export interface StockReconciliationItemIn { product_id:number; counted_quantity:number; }
export interface StockReconciliationIn { items:StockReconciliationItemIn[]; }
export interface RestaurantTable { id:number; name:string; seats:number; active?:boolean; }
export interface RestaurantTableNested { id:number; name:string; seats:number; }
export type CartItem={kind:"local";product:Product;quantity:number}|{kind:"server";itemId:number;productId:number;productName:string;price:number;lineTotal:number;quantity:number;batchId:number|null;sentAt:string|null};
export interface OrderItem { id:number; product_id:number; product_name:string; quantity:number; price:number; /* paisa */ line_total:number; /* paisa */ batch_id:number|null; sent_at:string|null; }
// Customers (Phase 3.2–3.5)
export interface Customer { id:number; name_display:string; phone_raw:string|null; phone_key:string|null; address:string|null; /* Phase 3.5: last used delivery address */ is_active:boolean; created_at:string; updated_at:string; }
export interface CustomerInfo { id:number; name_display:string; phone_raw:string|null; }
export interface UserNested { id:number; name:string; }
export interface CustomerSearchResult { id:number; name_display:string; phone_raw:string|null; address:string|null; is_active:boolean; order_count:number; /* Phase 3.5 */ paid_order_count:number; /* Phase 3.5 */ }
export interface CustomerCreateInput { name:string; phone?:string|null; address?:string|null; }
export interface CustomerUpdateInput { name?:string; phone?:string|null; address?:string|null; }
// Order status (Phase 7) — PAID | CANCELLED. One status field, no separate flag.
export type OrderStatus = "OPEN" | "PAID" | "CANCELLED";
export type CancellationReason = "CUSTOMER_CHANGED_ORDER" | "WRONG_ORDER" | "PAYMENT_ISSUE" | "DUPLICATE_ORDER" | "OTHER";
export interface OrderCancelInput { reason:CancellationReason; note?:string; }
export interface Order { id:number; order_number:string; order_type:OrderType; table_id?:number|null; table:RestaurantTableNested|null; customer:CustomerInfo|null; delivery_address:string|null; tax_rate:number|null; delivery_charge:number|null; /* paisa */ status:OrderStatus; subtotal:number; /* paisa */ discount:number; /* paisa */ tax:number; /* paisa */ total:number; /* paisa */ payment_method:PaymentMethod|null; amount_received:number; /* paisa */ change_amount:number; /* paisa */ created_at:string; paid_at:string|null; cancelled_at:string|null; cancelled_reason:string|null; items:OrderItem[]; performed_by?:UserNested|null; cancelled_by?:UserNested|null; }
// Dashboard (Phase 9) — real-time business metrics
export interface HourlySale { hour:number; revenue:number; /* paisa */ }
export interface TopProduct { product_name:string; quantity_sold:number; revenue:number; /* paisa */ }
export interface DashboardOverview { sales:number; /* paisa */ orders:number; cancelled:number; low_stock:number; hourly_sales:HourlySale[]; top_products:TopProduct[]; }
// Dashboard (Stage 8) — range-aware metrics with profit and staff attribution
export interface DailySale { date:string; revenue:number; /* paisa */ }
export interface StaffMetrics { user_id:number|null; user_name:string|null; sales:number; /* paisa */ orders:number; cancelled:number; discount_total:number; /* paisa */ }
export interface DashboardRange { range_type:string; window_start:string; window_end:string; sales:number; /* paisa */ sales_previous:number; profit:number; profit_margin_pct:number; orders_missing_cost:number; orders:number; average_order_value:number; /* paisa */ cash_orders:number; card_orders:number; other_orders:number; cash_sales:number; /* paisa */ card_sales:number; /* paisa */ discount_total:number; /* paisa */ discount_order_count:number; cancelled_count:number; cancelled_value:number; /* paisa */ dine_in_count:number; takeaway_count:number; delivery_count:number; low_stock_count:number; daily_sales:DailySale[]; hourly_sales:HourlySale[]; top_products:TopProduct[]; slow_products:TopProduct[]; per_staff:StaffMetrics[]; }
// Product Management (Phase 10)
export interface ProductCreateInput { category_id:number; name:string; price:number; /* paisa */ purchase_price?:number; /* paisa */ stock?:number; min_stock?:number; sku?:string; unit:string; image?:string; }
export interface ProductUpdateInput { category_id?:number; name?:string; price?:number; /* paisa */ purchase_price?:number; /* paisa */ min_stock?:number; sku?:string; unit?:string; image?:string; }
// Form state for AddProductModal — separate from API types because category_id can be unset during form entry
export interface ProductFormState { category_id:number|null; name:string; price:number; purchase_price?:number; stock?:number; min_stock?:number; sku?:string; unit:string; image?:string; }
// Authentication (Stage 7)
export interface User { id:number; name:string; can_cancel:boolean; can_discount:boolean; can_manage_settings:boolean; is_active:boolean; is_owner:boolean; created_at:string; }
