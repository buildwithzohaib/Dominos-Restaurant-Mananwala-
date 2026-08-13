from datetime import datetime
from decimal import Decimal
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
    price: Decimal
    stock: int
    image: str | None
    available: bool
    status: str
    sku: str
    min_stock: int
    unit: str
    purchase_price: Decimal
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
    order_type: Literal["DINE_IN", "TAKEAWAY", "DELIVERY"] = "TAKEAWAY"
    table_id: int | None = None
    items: list[OrderItemCreate] = Field(min_length=1)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    payment_method: Literal["CASH", "CARD", "OTHER"] = "CASH"
    amount_received: Decimal = Field(default=Decimal("0"), ge=0)

class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    product_name: str
    quantity: int
    price: Decimal
    line_total: Decimal

class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_number: str
    order_type: str
    table_id: int | None
    status: str
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    payment_method: str
    amount_received: Decimal
    change_amount: Decimal
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
    purchase_price: Decimal | None = Field(default=None, ge=0)
    price: Decimal | None = Field(default=None, ge=0)  # selling price -> writes the same Product.price POS reads

# --- Stock operations (Phase 4) ---------------------------------------------

class StockPurchaseIn(BaseModel):
    """Add Stock, upgraded from a bare quantity bump into a receiving operation:
    every purchase records who it came from and what it cost, in a StockMovement
    row created alongside the Product.stock update (see stock_service)."""
    quantity: int = Field(gt=0)
    purchase_price: Decimal | None = Field(default=None, ge=0)
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
    product_id: int
    product_name: str
    movement_type: str
    quantity_change: int
    reason: str
    supplier: str | None
    purchase_price: Decimal | None
    stock_before: int
    stock_after: int
    reference: str | None
    created_at: datetime

# --- Dashboard (Phase 9) ---

class TopProductItem(BaseModel):
    product_name: str
    quantity_sold: int
    revenue: Decimal

class HourlySaleItem(BaseModel):
    hour: int  # 0-23
    revenue: Decimal

class DashboardOverviewOut(BaseModel):
    sales: Decimal  # Today's total revenue from PAID orders
    orders: int  # Count of today's PAID orders
    cancelled: int  # Count of today's CANCELLED orders
    low_stock: int  # Count of products in LOW_STOCK status
    hourly_sales: list[HourlySaleItem]  # Hourly breakdown of today's sales
    top_products: list[TopProductItem]  # Top 5 selling products by quantity

# --- Product Management (Phase 10) ---

class ProductCreate(BaseModel):
    category_id: int
    name: str = Field(min_length=1, max_length=150)
    price: Decimal = Field(gt=0)
    purchase_price: Decimal | None = Field(default=None, ge=0)
    stock: int = Field(default=0, ge=0)
    min_stock: int = Field(default=5, ge=0)
    sku: str | None = Field(default=None, max_length=50)
    unit: str = Field(min_length=1, max_length=30)
    image: str | None = Field(default=None, max_length=500)

class ProductUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=150)
    price: Decimal | None = Field(default=None, gt=0)
    purchase_price: Decimal | None = Field(default=None, ge=0)
    min_stock: int | None = Field(default=None, ge=0)
    sku: str | None = Field(default=None, max_length=50)
    unit: str | None = Field(default=None, min_length=1, max_length=30)
    image: str | None = Field(default=None, max_length=500)
