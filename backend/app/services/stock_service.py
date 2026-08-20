from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from app.models.models import Product, StockMovement
from app.schemas.schemas import StockAdjustmentIn, StockPurchaseIn, StockReconciliationIn

REASON_LABELS = {
    "DAMAGED": "Damaged",
    "EXPIRED": "Expired",
    "LOST": "Lost",
    "MANUAL_CORRECTION": "Manual Correction",
    "OTHER": "Other",
}


def add_purchase_stock(db: Session, product_id: int, payload: StockPurchaseIn) -> Product:
    """Add Stock, upgraded (Phase 4) into a receiving operation: validates the
    product/quantity/price, records who supplied it, updates Product.stock — the one
    authoritative current-stock value — and writes a matching PURCHASE ledger row.

    The stock mutation is a single atomic `stock = stock + quantity` UPDATE (like
    order_service's sale path), not a Python read-modify-write — two concurrent Add
    Stock calls on the same product can't silently lose one of them the way a plain
    `product.stock = product.stock + qty` assignment could under interleaved reads.
    stock_before is derived from the post-update value rather than a separate read,
    so it's correct regardless of what else was happening concurrently.
    """
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found.")

    supplier = payload.supplier.strip()
    if not supplier:
        raise HTTPException(400, "Supplier is required for a stock purchase.")

    values = {"stock": Product.stock + payload.quantity, "updated_at": datetime.utcnow()}
    if payload.purchase_price is not None:
        # This purchase's cost becomes the product's latest acquisition cost. The
        # customer-facing selling price (Product.price) is a completely separate
        # field and is never touched here — see Phase 3/4 "Purchase Price ≠ Selling
        # Price".
        values["purchase_price"] = payload.purchase_price

    db.execute(update(Product).where(Product.id == product_id).values(**values))
    db.refresh(product)
    stock_after = product.stock
    stock_before = stock_after - payload.quantity

    movement = StockMovement(
        item_type="PRODUCT",
        item_id=product.id,
        item_name=product.name_display,
        movement_type="PURCHASE",
        quantity_change=payload.quantity,
        reason="Purchase",
        supplier=supplier,
        purchase_price=payload.purchase_price,
        stock_before=stock_before,
        stock_after=stock_after,
    )
    db.add(movement)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "Could not save the stock movement, please try again.")
    db.refresh(product)
    return product


def adjust_stock(db: Session, product_id: int, payload: StockAdjustmentIn) -> Product:
    """Stock Adjustment: a signed, reasoned correction to on-hand stock (damage,
    expiry, loss, manual correction, other). Cannot drive stock negative.

    Same atomic-UPDATE approach as add_purchase_stock, plus the WHERE clause re-checks
    `stock + quantity_change >= 0` at write time — mirroring order_service's overselling
    guard — so two concurrent adjustments can't both read a stock high enough to allow
    a negative-result adjustment and then both apply it.
    """
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found.")

    label = REASON_LABELS[payload.reason]
    if payload.reason == "OTHER" and payload.note and payload.note.strip():
        label = f"Other: {payload.note.strip()}"

    result = db.execute(
        update(Product)
        .where(Product.id == product_id, Product.stock + payload.quantity_change >= 0)
        .values(stock=Product.stock + payload.quantity_change, updated_at=datetime.utcnow())
    )
    if result.rowcount == 0:
        db.rollback()
        current = db.get(Product, product_id)
        available = current.stock if current else 0
        raise HTTPException(
            400, f"Insufficient stock for this adjustment. Current stock: {available}."
        )

    db.refresh(product)
    stock_after = product.stock
    stock_before = stock_after - payload.quantity_change

    movement = StockMovement(
        item_type="PRODUCT",
        item_id=product.id,
        item_name=product.name_display,
        movement_type="ADJUSTMENT",
        quantity_change=payload.quantity_change,
        reason=label,
        supplier=None,
        purchase_price=None,
        stock_before=stock_before,
        stock_after=stock_after,
    )
    db.add(movement)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "Could not save the stock movement, please try again.")
    db.refresh(product)
    return product


def list_movements(
    db: Session,
    search: str | None = None,
    movement_type: str | None = None,
    date: str | None = None,
) -> list[StockMovement]:
    query = db.query(StockMovement)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(StockMovement.item_name.ilike(term), StockMovement.supplier.ilike(term))
        )
    if movement_type and movement_type.strip():
        query = query.filter(StockMovement.movement_type == movement_type.strip().upper())
    if date and date.strip():
        # Plain day-bucket filter (YYYY-MM-DD) — deliberately simple per Phase 4 §14
        # ("do not build advanced analytics yet").
        try:
            day = datetime.strptime(date.strip(), "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, "Date filter must be in YYYY-MM-DD format.")
        day_start = datetime(day.year, day.month, day.day)
        query = query.filter(
            StockMovement.created_at >= day_start,
            StockMovement.created_at < day_start + timedelta(days=1),
        )
    return query.order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).all()


def reconcile_stock(db: Session, payload: StockReconciliationIn) -> list[StockMovement]:
    """Batch stock reconciliation from physical count. For each row where
    counted_quantity differs from system stock, computes the delta and writes
    one ADJUSTMENT StockMovement. Rows where counted == system are skipped
    (no movement written).

    All adjustments happen in a single transaction: either all succeed or all
    rollback. If any product_id is invalid, NO changes are written.

    Args:
        db: database session
        payload: StockReconciliationIn with items list of {product_id, counted_quantity}

    Returns:
        List of created StockMovement rows (one per changed product)

    Raises:
        HTTPException if any product not found, concurrent changes detected,
        or if counted quantity would result in negative stock
    """
    # PHASE 1: Validate all product_ids exist and calculate deltas.
    # NO database writes yet. If any product_id is invalid, fail immediately
    # without touching the database (atomic guarantee + privacy guarantee).
    products_to_reconcile = []  # List of (item, product, stock_before, delta)

    for item in payload.items:
        product = db.get(Product, item.product_id)
        if not product:
            raise HTTPException(404, f"Product ID {item.product_id} not found")

        stock_before = product.stock
        delta = item.counted_quantity - stock_before

        # Skip unchanged rows, but track changed ones for Phase 2
        if delta != 0:
            products_to_reconcile.append((item, product, stock_before, delta))

    # If no changes needed, return empty list
    if not products_to_reconcile:
        return []

    # PHASE 2: Apply all updates in a single transaction.
    # At this point, all product_ids are known to exist.
    movements = []

    for item, product, stock_before, delta in products_to_reconcile:
        # Atomic UPDATE with WHERE guard (identical to adjust_stock's guard)
        result = db.execute(
            update(Product)
            .where(Product.id == item.product_id, Product.stock + delta >= 0)
            .values(stock=Product.stock + delta, updated_at=datetime.utcnow())
        )
        if result.rowcount == 0:
            db.rollback()
            current = db.get(Product, item.product_id)
            name = current.name_display if current else product.name_display
            raise HTTPException(
                400, f"Cannot reconcile {name} — concurrent stock changes detected, please retry the count"
            )

        db.refresh(product)
        stock_after = product.stock

        movement = StockMovement(
            item_type="PRODUCT",
            item_id=product.id,
            item_name=product.name_display,
            movement_type="ADJUSTMENT",
            quantity_change=delta,
            reason="Stock count reconciliation",
            supplier=None,
            purchase_price=None,
            stock_before=stock_before,
            stock_after=stock_after,
        )
        db.add(movement)
        movements.append(movement)

    # Commit all adjustments in one transaction
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "Could not save reconciliation, please try again")

    # Refresh movements to populate id and created_at
    for m in movements:
        db.refresh(m)

    return movements
