from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
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
    delivery_charge: Mapped[int] = mapped_column(Integer, default=0)  # paisa, default 0 (no delivery charge)
    day_starts_at: Mapped[str] = mapped_column(String(5), default="06:00")  # HH:MM format
    receipt_footer_text: Mapped[str] = mapped_column(String(200), default="Please visit us again.")
    theme: Mapped[str] = mapped_column(String(30), default="amber")  # hidden theme choice; one of 12 known keys
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint('id = 1', name='check_single_row'),
    )

class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_raw: Mapped[str] = mapped_column(String(255))  # exactly as typed, audit trail
    name_display: Mapped[str] = mapped_column(String(255))  # whitespace-normalized, for UI/display
    name_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)  # lowercase alphanumeric, dedup detection
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    products: Mapped[list["Product"]] = relationship(back_populates="category")

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    name_raw: Mapped[str] = mapped_column(String(255))  # exactly as typed, audit trail
    name_display: Mapped[str] = mapped_column(String(255))  # whitespace-normalized, for UI/display
    name_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)  # lowercase alphanumeric, dedup detection
    price: Mapped[int] = mapped_column(Integer)  # single authoritative selling price: POS/cart/receipt all read this
    stock: Mapped[int] = mapped_column(Integer, default=0)  # single authoritative current-stock value
    image: Mapped[str | None] = mapped_column(String(500), nullable=True)  # filename only, e.g. "5.jpg"
    image_hash: Mapped[str | None] = mapped_column(String(32), nullable=True)  # MD5 hash of image for cache-busting
    available: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Inventory fields (Phase 3) — extend the existing Product row, no separate inventory table ---
    sku: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    min_stock: Mapped[int] = mapped_column(Integer, default=5)
    unit: Mapped[str] = mapped_column(String(30), default="Piece")
    purchase_price: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # --- Product type (Phase 11) — 'PRODUCT' for regular items, 'DEAL' for combo products ---
    product_type: Mapped[str] = mapped_column(String(20), default="PRODUCT")

    category: Mapped["Category"] = relationship(back_populates="products")
    sizes: Mapped[list["ProductSize"]] = relationship(back_populates="product", cascade="all, delete-orphan")

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

class ProductSize(Base):
    """Size variants for a product. Each product can have multiple sizes (e.g., Small/Medium/Large)
    with different prices. Sizes are product-specific, not global.
    Rule 5 (polymorphic stock ledger) reserves size tracking for Phase 12+; this phase only affects price.
    """
    __tablename__ = "product_sizes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))  # e.g., "Small", "F1", "Roll"
    price: Mapped[int] = mapped_column(Integer)  # selling price in paisa, same convention as Product.price
    sort_order: Mapped[int] = mapped_column(Integer)  # display order in menu (1, 2, 3...), not alphabetical
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product: Mapped["Product"] = relationship(back_populates="sizes")

    __table_args__ = (
        UniqueConstraint('product_id', 'name', name='uq_product_size_name'),
    )

class DealComponent(Base):
    """A component of a deal product. Each row defines one item that must be included
    in the deal (e.g., Pizza + Drink + Burger). product_id points to the DEAL
    (product with type='DEAL'), component_product_id points to the component product.
    If size_id is specified, that component must use that size."""
    __tablename__ = "deal_components"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))  # the deal (product with type='DEAL')
    component_product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))  # the component product
    quantity: Mapped[int] = mapped_column(Integer)  # qty required, e.g., 1
    size_id: Mapped[int | None] = mapped_column(ForeignKey("product_sizes.id"), nullable=True)  # mandatory size if specified
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # display order in deal detail
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('ix_deal_components_product_id', 'product_id'),
        Index('ix_deal_components_component_product_id', 'component_product_id'),
        UniqueConstraint('product_id', 'component_product_id', 'size_id', name='uq_deal_component'),
    )

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

class Customer(Base):
    """Customer information for recurring orders and delivery.
    Follows Rule 9 text normalization for names, phone_service for phone numbers.

    address: Convenience prefill for delivery orders (Phase 3.5). Stores the last
    delivery address used with this customer so repeat customers don't re-type it.
    This is NOT the source of truth: order.delivery_address (Rule 7 snapshot) is.
    Automatically updated when a DELIVERY order is confirmed; manually editable.
    Nullable because not all customers use delivery."""
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Name: three-field normalization (Rule 9)
    name_raw: Mapped[str] = mapped_column(String(255))  # exactly as typed, audit trail
    name_display: Mapped[str] = mapped_column(String(255))  # Title Case with exceptions, for UI
    name_key: Mapped[str] = mapped_column(String(255), index=True)  # lowercase no-space, for search; NOT unique (multiple "Ali"s OK)
    # Phone: two fields (no display field; formatted on-demand)
    phone_raw: Mapped[str | None] = mapped_column(String(20), nullable=True)  # as typed by user
    phone_key: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)  # normalized 0XXX; NOT unique (family members share)
    # Address: convenience prefill only (Rule 7 source of truth is order.delivery_address)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)  # last used delivery address, for prefilling; NOT authoritative
    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # soft delete (Rule 6)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class User(Base):
    """User accounts for POS staff. Bootstrap: first user becomes Owner."""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    pin: Mapped[str] = mapped_column(String(100), nullable=False)  # bcrypt hash (~60 chars); DB declares VARCHAR(10) but SQLite ignores length
    can_cancel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_discount: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_manage_settings: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('name', 'pin', name='uq_users_name_pin'),
    )

class UserSession(Base):
    """Active login sessions. 90-day safety net expiry; no UX-facing timeout."""
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # 90-day safety net

    __table_args__ = (
        Index('ix_sessions_token', 'token', unique=True),
        Index('ix_sessions_user_id', 'user_id'),
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
    # OPEN | PAID | CANCELLED — the one status field for an order.
    # OPEN (Stage 4) is a dine-in running tab: items may still be added, and the
    # order has not been paid yet. It becomes PAID or CANCELLED exactly once.
    # Default stays "PAID" so the existing single-shot takeaway/delivery flow
    # (create + pay in one call) is unchanged; create_open_order() sets "OPEN"
    # explicitly.
    status: Mapped[str] = mapped_column(String(30), default="PAID")
    subtotal: Mapped[int] = mapped_column(Integer)
    discount: Mapped[int] = mapped_column(Integer, default=0)
    tax: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer)
    # CASH | CARD | OTHER, or NULL while the order is still OPEN (not yet paid).
    # NULL is the only representation of "unpaid" — never use an empty string.
    payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    amount_received: Mapped[int] = mapped_column(Integer, default=0)
    change_amount: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    # --- Cancellation metadata (Phase 7) — a cancelled order is never deleted, only
    # flipped to status="CANCELLED" with these two fields recorded alongside it. ---
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # --- Payment timestamp (Stage 4) — records when the order was paid, NULL while OPEN ---
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # --- Customer and delivery (Phase 3.3-3.4) — snapshots per Rule 7 ---
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)  # NULL for walk-ins
    delivery_address: Mapped[str | None] = mapped_column(String(300), nullable=True)  # snapshot of address at order time, NULL for non-delivery
    tax_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)  # basis points at order time (e.g., 1600 for 16%), Rule 7 snapshot
    delivery_charge: Mapped[int | None] = mapped_column(Integer, nullable=True)  # paisa at order time (e.g., 20000 for Rs. 200), Rule 7 snapshot; NULL for non-delivery
    # --- User attribution (Stage 7) — who processed payment/discount and who cancelled ---
    # ForeignKey declared for ORM joins only; no database-level constraint (SQLite cannot
    # add FK via ALTER, and does not enforce foreign keys by default).
    performed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # User who paid/discounted
    cancel_order_performed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # User who cancelled
    table: Mapped["RestaurantTable | None"] = relationship()
    customer: Mapped["Customer | None"] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    performed_by: Mapped["User | None"] = relationship(foreign_keys=[performed_by_user_id])
    cancelled_by: Mapped["User | None"] = relationship(foreign_keys=[cancel_order_performed_by_user_id])

    # Stage 4 A1: at most one OPEN order per table. PAID and CANCELLED rows are
    # excluded by the WHERE clause, so a table can be re-seated any number of times.
    # Declared here as well as in migration ad8ba306eabb so that databases built by
    # Base.metadata.create_all() (the test suite) also get the constraint —
    # otherwise a "reject second OPEN order" test would pass without enforcing it.
    # Must be Index, not UniqueConstraint: UniqueConstraint ignores sqlite_where and
    # would create an unconditional unique index, limiting each table to one order
    # for all time.
    __table_args__ = (
        Index('ix_one_open_per_table', 'table_id', unique=True,
              sqlite_where=text("status = 'OPEN'")),
    )

class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(150))
    size_name: Mapped[str | None] = mapped_column(String(100), nullable=True)  # size variant name (e.g., "Small"), NULL for unsized products
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Integer)
    line_total: Mapped[int] = mapped_column(Integer)
    # --- Stage 4: KOT batching ---
    # batch_id: NULL = PENDING (not sent to kitchen yet); 1, 2, 3... = sent in that
    # batch. Stock is deducted once per batch when it is sent (Rule 8), not on payment.
    batch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # sent_at: timestamp the batch was sent to the kitchen; NULL while PENDING.
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # --- Stage 8: Cost snapshot ---
    # cost in paisa at the moment the item was added; NULL for items created before Stage 8
    cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # --- Phase 11: Deal support ---
    # deal_id: if this line is a deal, points to product with type='DEAL'; NULL for regular items
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    # price_override: the deal's standard price at sale time (for audit), NULL if charged the standard price
    price_override: Mapped[int | None] = mapped_column(Integer, nullable=True)

    order: Mapped["Order"] = relationship(back_populates="items")
    components: Mapped[list["OrderItemComponent"]] = relationship(back_populates="order_item", cascade="all, delete-orphan")


class OrderItemComponent(Base):
    """Snapshot of a deal component as it was added to an order. Tracks which
    components were included, which were removed, and which sizes were swapped.
    Serves as the audit record of what actually went into the deal at sale time.
    One row per component per order line."""
    __tablename__ = "order_item_components"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"))  # ties to the deal line
    deal_component_id: Mapped[int] = mapped_column(ForeignKey("deal_components.id"))  # which component in deal definition
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))  # the component product
    product_name: Mapped[str] = mapped_column(String(150))  # snapshot, never changes after creation
    quantity: Mapped[int] = mapped_column(Integer)  # qty of this component
    size_id: Mapped[int | None] = mapped_column(ForeignKey("product_sizes.id"), nullable=True)  # actual size used (may differ from deal definition)
    was_removed: Mapped[bool] = mapped_column(Boolean, default=False)  # did cashier remove this component?
    removed_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)  # why removed (e.g., "Out of stock")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order_item: Mapped["OrderItem"] = relationship(back_populates="components")

    __table_args__ = (
        Index('ix_order_item_components_order_item_id', 'order_item_id'),
        Index('ix_order_item_components_deal_component_id', 'deal_component_id'),
        Index('ix_order_item_components_product_id', 'product_id'),
    )
