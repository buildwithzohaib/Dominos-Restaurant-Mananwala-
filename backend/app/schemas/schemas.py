from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    active: bool

class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category_id: int
    name: str
    price: int  # paisa
    stock: int
    image: str | None
    available: bool
    status: str
    sku: str
    min_stock: int
    unit: str
    purchase_price: int  # paisa
    stock_status: str
    updated_at: datetime

class TableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    seats: int
    active: bool

class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)

class OrderCreate(BaseModel):
    """Create a new order. All money values in paisa; tax_rate in basis points."""
    order_type: Literal["DINE_IN", "TAKEAWAY", "DELIVERY"] = "TAKEAWAY"
    table_id: int | None = None
    items: list[OrderItemCreate] = Field(min_length=1)
    discount: int = Field(default=0, ge=0)  # paisa
    tax_rate: int = Field(default=0, ge=0, le=10000)  # basis points
    payment_method: Literal["CASH", "CARD", "OTHER"] = "CASH"
    amount_received: int = Field(default=0, ge=0)  # paisa

class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    product_name: str
    quantity: int
    price: int  # paisa
    line_total: int  # paisa

class OrderOut(BaseModel):
    """Order details. All money values in paisa."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_number: str
    order_type: str
    table_id: int | None
    status: str
    subtotal: int  # paisa
    discount: int  # paisa
    tax: int  # paisa
    total: int  # paisa
    payment_method: str
    amount_received: int  # paisa
    change_amount: int  # paisa, can be negative
    created_at: datetime
    cancelled_at: datetime | None
    cancelled_reason: str | None
    items: list[OrderItemOut]

# --- Order cancellation (Phase 7) -------------------------------------------

CancellationReason = Literal[
    "CUSTOMER_CHANGED_ORDER", "WRONG_ORDER", "PAYMENT_ISSUE", "DUPLICATE_ORDER", "OTHER"
]

class OrderCancelIn(BaseModel):
    reason: CancellationReason
    note: str | None = Field(default=None, max_length=300)

class InventoryUpdate(BaseModel):
    name: str | None = None
    sku: str | None = Field(default=None, max_length=50)
    min_stock: int | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=30)
    purchase_price: int | None = Field(default=None, ge=0)  # paisa
    price: int | None = Field(default=None, ge=0)  # paisa, selling price -> writes the same Product.price POS reads

# --- Stock operations (Phase 4) ---------------------------------------------

class StockPurchaseIn(BaseModel):
    """Add Stock, upgraded from a bare quantity bump into a receiving operation:
    every purchase records who it came from and what it cost, in a StockMovement
    row created alongside the Product.stock update (see stock_service).
    purchase_price in paisa."""
    quantity: int = Field(gt=0)
    purchase_price: int | None = Field(default=None, ge=0)  # paisa
    supplier: str = Field(min_length=1, max_length=150)

AdjustmentReason = Literal["DAMAGED", "EXPIRED", "LOST", "MANUAL_CORRECTION", "OTHER"]

class StockAdjustmentIn(BaseModel):
    quantity_change: int  # signed: +5 correction, -2 damage — zero is rejected below
    reason: AdjustmentReason
    note: str | None = Field(default=None, max_length=300)

    @field_validator("quantity_change")
    @classmethod
    def not_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("Adjustment quantity cannot be zero.")
        return value

class StockMovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    item_type: str  # 'PRODUCT' | 'INGREDIENT'
    item_id: int
    item_name: str
    movement_type: str
    quantity_change: int
    reason: str
    supplier: str | None
    purchase_price: int | None  # paisa
    stock_before: int
    stock_after: int
    reference: str | None
    created_at: datetime

# --- Dashboard (Phase 9) ---

class TopProductItem(BaseModel):
    product_name: str
    quantity_sold: int
    revenue: int  # paisa

class HourlySaleItem(BaseModel):
    hour: int  # 0-23
    revenue: int  # paisa

class DashboardOverviewOut(BaseModel):
    sales: int  # paisa, today's total revenue from PAID orders
    orders: int  # Count of today's PAID orders
    cancelled: int  # Count of today's CANCELLED orders
    low_stock: int  # Count of products in LOW_STOCK status
    hourly_sales: list[HourlySaleItem]  # Hourly breakdown of today's sales
    top_products: list[TopProductItem]  # Top 5 selling products by quantity

# --- Product Management (Phase 10) ---

class ProductCreate(BaseModel):
    """Create a new product. price and purchase_price in paisa."""
    category_id: int
    name: str = Field(min_length=1, max_length=150)
    price: int = Field(gt=0)  # paisa
    purchase_price: int | None = Field(default=None, ge=0)  # paisa
    stock: int = Field(default=0, ge=0)
    min_stock: int = Field(default=5, ge=0)
    sku: str | None = Field(default=None, max_length=50)
    unit: str = Field(min_length=1, max_length=30)
    image: str | None = Field(default=None, max_length=500)

class ProductUpdate(BaseModel):
    """Update product. price and purchase_price in paisa."""
    category_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=150)
    price: int | None = Field(default=None, gt=0)  # paisa
    purchase_price: int | None = Field(default=None, ge=0)  # paisa
    min_stock: int | None = Field(default=None, ge=0)
    sku: str | None = Field(default=None, max_length=50)
    unit: str | None = Field(default=None, min_length=1, max_length=30)
    image: str | None = Field(default=None, max_length=500)
