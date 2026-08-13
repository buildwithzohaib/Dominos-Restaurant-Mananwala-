export type OrderType = "DINE_IN" | "TAKEAWAY" | "DELIVERY";
export type PaymentMethod = "CASH" | "CARD" | "OTHER";
export type StockStatus = "IN_STOCK" | "LOW_STOCK" | "OUT_OF_STOCK";
export interface Category { id:number; name:string; active:boolean; }
// Inventory fields (Phase 3) live on the same Product row the POS/cart/receipt already
// read — sku/min_stock/unit/purchase_price/stock_status/updated_at are additive, and
// price/stock remain the single authoritative selling-price/current-stock values.
export interface Product { id:number; category_id:number; name:string; price:number; stock:number; image?:string|null; available:boolean; status:string; sku:string; min_stock:number; unit:string; purchase_price:number; stock_status:StockStatus; updated_at:string; }
export interface InventoryUpdateInput { name?:string; sku?:string; min_stock?:number; unit?:string; purchase_price?:number; price?:number; }
// Stock operations (Phase 4–8) — every change to Product.stock writes one of
// these ledger rows in the same backend transaction; Product.stock stays the only
// authoritative current-stock value, this just explains its history.
export type MovementType = "PURCHASE" | "ADJUSTMENT" | "SALE" | "CANCELLATION";
export type AdjustmentReason = "DAMAGED" | "EXPIRED" | "LOST" | "MANUAL_CORRECTION" | "OTHER";
export interface StockPurchaseInput { quantity:number; purchase_price?:number; supplier:string; }
export interface StockAdjustmentInput { quantity_change:number; reason:AdjustmentReason; note?:string; }
export interface StockMovement { id:number; product_id:number; product_name:string; movement_type:MovementType; quantity_change:number; reason:string; supplier?:string|null; purchase_price?:number|null; stock_before:number; stock_after:number; reference?:string|null; created_at:string; }
export interface RestaurantTable { id:number; name:string; seats:number; active:boolean; }
export interface CartItem { product:Product; quantity:number; }
export interface OrderItem { id:number; product_id:number; product_name:string; quantity:number; price:number; line_total:number; }
// Order status (Phase 7) — PAID | CANCELLED. One status field, no separate flag.
export type OrderStatus = "PAID" | "CANCELLED";
export type CancellationReason = "CUSTOMER_CHANGED_ORDER" | "WRONG_ORDER" | "PAYMENT_ISSUE" | "DUPLICATE_ORDER" | "OTHER";
export interface OrderCancelInput { reason:CancellationReason; note?:string; }
export interface Order { id:number; order_number:string; order_type:OrderType; table_id?:number|null; status:OrderStatus; subtotal:number; discount:number; tax:number; total:number; payment_method:PaymentMethod; amount_received:number; change_amount:number; created_at:string; cancelled_at?:string|null; cancelled_reason?:string|null; items:OrderItem[]; }
// Dashboard (Phase 9) — real-time business metrics
export interface HourlySale { hour:number; revenue:number; }
export interface TopProduct { product_name:string; quantity_sold:number; revenue:number; }
export interface DashboardOverview { sales:number; orders:number; cancelled:number; low_stock:number; hourly_sales:HourlySale[]; top_products:TopProduct[]; }
