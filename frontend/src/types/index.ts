export type OrderType = "DINE_IN" | "TAKEAWAY" | "DELIVERY";
export type PaymentMethod = "CASH" | "CARD" | "OTHER";
export type StockStatus = "IN_STOCK" | "LOW_STOCK" | "OUT_OF_STOCK";
// Settings (Task 1.1) — single immutable row with restaurant configuration
export interface Settings { id:number; restaurant_name:string; restaurant_address:string; restaurant_phone:string; currency_symbol:string; tax_rate:number; /* basis points */ tax_enabled:boolean; delivery_charge:number; /* paisa */ day_starts_at:string; /* HH:MM format */ receipt_footer_text:string; created_at:string; updated_at:string; }
export interface SettingsUpdate { restaurant_name?:string; restaurant_address?:string; restaurant_phone?:string; currency_symbol?:string; tax_rate?:number; /* basis points */ tax_enabled?:boolean; delivery_charge?:number; /* paisa */ day_starts_at?:string; receipt_footer_text?:string; }
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
export interface RestaurantTable { id:number; name:string; seats:number; active:boolean; }
export type CartItem={kind:"local";product:Product;quantity:number}|{kind:"server";itemId:number;productId:number;productName:string;price:number;lineTotal:number;quantity:number;batchId:number|null;sentAt:string|null};
export interface OrderItem { id:number; product_id:number; product_name:string; quantity:number; price:number; /* paisa */ line_total:number; /* paisa */ batch_id:number|null; sent_at:string|null; }
// Customers (Phase 3.2–3.5)
export interface Customer { id:number; name_display:string; phone_raw:string|null; phone_key:string|null; address:string|null; /* Phase 3.5: last used delivery address */ is_active:boolean; created_at:string; updated_at:string; }
export interface CustomerInfo { id:number; name_display:string; phone_raw:string|null; }
export interface CustomerSearchResult { id:number; name_display:string; phone_raw:string|null; address:string|null; is_active:boolean; order_count:number; /* Phase 3.5 */ paid_order_count:number; /* Phase 3.5 */ }
export interface CustomerCreateInput { name:string; phone?:string|null; address?:string|null; }
export interface CustomerUpdateInput { name?:string; phone?:string|null; address?:string|null; }
// Order status (Phase 7) — PAID | CANCELLED. One status field, no separate flag.
export type OrderStatus = "PAID" | "CANCELLED";
export type CancellationReason = "CUSTOMER_CHANGED_ORDER" | "WRONG_ORDER" | "PAYMENT_ISSUE" | "DUPLICATE_ORDER" | "OTHER";
export interface OrderCancelInput { reason:CancellationReason; note?:string; }
export interface Order { id:number; order_number:string; order_type:OrderType; table_id?:number|null; customer:CustomerInfo|null; delivery_address:string|null; tax_rate:number|null; delivery_charge:number|null; /* paisa */ status:OrderStatus; subtotal:number; /* paisa */ discount:number; /* paisa */ tax:number; /* paisa */ total:number; /* paisa */ payment_method:PaymentMethod; amount_received:number; /* paisa */ change_amount:number; /* paisa */ created_at:string; cancelled_at?:string|null; cancelled_reason?:string|null; items:OrderItem[]; }
// Dashboard (Phase 9) — real-time business metrics
export interface HourlySale { hour:number; revenue:number; /* paisa */ }
export interface TopProduct { product_name:string; quantity_sold:number; revenue:number; /* paisa */ }
export interface DashboardOverview { sales:number; /* paisa */ orders:number; cancelled:number; low_stock:number; hourly_sales:HourlySale[]; top_products:TopProduct[]; }
// Product Management (Phase 10)
export interface ProductCreateInput { category_id:number; name:string; price:number; /* paisa */ purchase_price?:number; /* paisa */ stock?:number; min_stock?:number; sku?:string; unit:string; image?:string; }
export interface ProductUpdateInput { category_id?:number; name?:string; price?:number; /* paisa */ purchase_price?:number; /* paisa */ min_stock?:number; sku?:string; unit?:string; image?:string; }
