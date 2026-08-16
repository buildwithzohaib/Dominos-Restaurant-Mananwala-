from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Settings(Base):
    """Single-row settings table. id=1 enforced by CHECK constraint + DELETE trigger.
    Never create a second row — the constraint and trigger prevent it."""
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    restaurant_name: Mapped[str] = mapped_column(String(150), default="My Restaurant")
    restaurant_address: Mapped[str] = mapped_column(String(300), default="")
    restaurant_phone: Mapped[str] = mapped_column(String(20), default="")
    currency_symbol: Mapped[str] = mapped_column(String(10), default="Rs. ")
    tax_rate: Mapped[int] = mapped_column(Integer, default=0)  # basis points (1600 = 16%)
    tax_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    day_starts_at: Mapped[str] = mapped_column(String(5), default="06:00")  # HH:MM format
    receipt_footer_text: Mapped[str] = mapped_column(String(200), default="Please visit us again.")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint('id = 1', name='check_single_row'),
    )

class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    products: Mapped[list["Product"]] = relationship(back_populates="category", cascade="all, delete-orphan")

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    name: Mapped[str] = mapped_column(String(150), index=True)
    price: Mapped[int] = mapped_column(Integer)  # single authoritative selling price: POS/cart/receipt all read this
    stock: Mapped[int] = mapped_column(Integer, default=0)  # single authoritative current-stock value
    image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Inventory fields (Phase 3) — extend the existing Product row, no separate inventory table ---
    sku: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    min_stock: Mapped[int] = mapped_column(Integer, default=5)
    unit: Mapped[str] = mapped_column(String(30), default="Piece")
    purchase_price: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category: Mapped["Category"] = relationship(back_populates="products")

    @property
    def status(self) -> str:
        """Legacy two-state POS availability label, kept for backward compatibility."""
        return "In Stock" if self.available and self.stock > 0 else "Out of Stock"

    @property
    def stock_status(self) -> str:
        """Three-state inventory status, always derived from stock vs. min_stock."""
        if self.stock <= 0:
            return "OUT_OF_STOCK"
        if self.stock <= self.min_stock:
            return "LOW_STOCK"
        return "IN_STOCK"

class StockMovement(Base):
    """Task 0.7 ledger (polymorphic) — every stock change for products or ingredients
    writes one row here in the same transaction that updates the current stock value.
    Uses item_type ('PRODUCT' | 'INGREDIENT') + item_id to identify the item.
    Task 0.8 (ingredients + recipes) will add Ingredient model; stock_movements will track both."""
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Polymorphic identity: 'PRODUCT' | 'INGREDIENT'
    item_type: Mapped[str] = mapped_column(String(20))
    # The item's id in its respective table (products.id or ingredients.id in Stage 6)
    item_id: Mapped[int] = mapped_column(Integer)
    # Snapshot, not a live join — product or ingredient name at the time of movement,
    # so renaming an item later never rewrites what an audit record said at the time.
    item_name: Mapped[str] = mapped_column(String(150))
    # PURCHASE | ADJUSTMENT | SALE | CANCELLATION. RETURN/REFUND/WASTE are reserved
    # for a future phase and deliberately not implemented here.
    movement_type: Mapped[str] = mapped_column(String(20), index=True)
    quantity_change: Mapped[int] = mapped_column(Integer)  # signed: +50 purchase, -2 damage, +5 correction
    reason: Mapped[str] = mapped_column(String(200))  # e.g. "Purchase", "Damaged", "Other: <note>"
    supplier: Mapped[str | None] = mapped_column(String(150), nullable=True)
    purchase_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stock_before: Mapped[int] = mapped_column(Integer)
    stock_after: Mapped[int] = mapped_column(Integer)
    reference: Mapped[str | None] = mapped_column(String(50), nullable=True)  # reserved for a future SALE movement's order_number
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('ix_stock_movements_item_type_item_id', 'item_type', 'item_id'),
    )

class RestaurantTable(Base):
    __tablename__ = "restaurant_tables"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    seats: Mapped[int] = mapped_column(Integer, default=4)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    order_type: Mapped[str] = mapped_column(String(30), default="TAKEAWAY")
    table_id: Mapped[int | None] = mapped_column(ForeignKey("restaurant_tables.id"), nullable=True)
    # PAID | CANCELLED — the one status field for an order (Phase 7). Renamed from
    # the old "COMPLETED" default to match the terminology Phase 7's Orders page
    # uses; see seed.py's migration for the one-time backfill of pre-existing rows.
    status: Mapped[str] = mapped_column(String(30), default="PAID")
    subtotal: Mapped[int] = mapped_column(Integer)
    discount: Mapped[int] = mapped_column(Integer, default=0)
    tax: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer)
    payment_method: Mapped[str] = mapped_column(String(30))
    amount_received: Mapped[int] = mapped_column(Integer, default=0)
    change_amount: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    # --- Cancellation metadata (Phase 7) — a cancelled order is never deleted, only
    # flipped to status="CANCELLED" with these two fields recorded alongside it. ---
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    table: Mapped["RestaurantTable | None"] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(150))
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Integer)
    line_total: Mapped[int] = mapped_column(Integer)
    order: Mapped["Order"] = relationship(back_populates="items")
