from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from app.models.models import Product, StockMovement
from app.schemas.schemas import StockAdjustmentIn, StockPurchaseIn

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
