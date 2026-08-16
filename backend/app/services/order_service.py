from collections import defaultdict
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.models import Order, OrderItem, Product, RestaurantTable, StockMovement
from app.schemas.schemas import OrderCancelIn, OrderCreate

CANCEL_REASON_LABELS = {
    "CUSTOMER_CHANGED_ORDER": "Customer changed order",
    "WRONG_ORDER": "Wrong order",
    "PAYMENT_ISSUE": "Payment issue",
    "DUPLICATE_ORDER": "Duplicate order",
    "OTHER": "Other",
}

def create_order(db: Session, payload: OrderCreate) -> Order:
    if payload.order_type == "DINE_IN" and payload.table_id is None:
        raise HTTPException(400, "A table is required for dine-in orders.")
    if payload.order_type != "DINE_IN" and payload.table_id is not None:
        raise HTTPException(400, "Only dine-in orders can have a table.")
    if payload.table_id is not None:
        table = db.get(RestaurantTable, payload.table_id)
        if not table or not table.active:
            raise HTTPException(400, "Selected table is not available.")

    # Aggregate by product in case the same product appears on more than one line,
    # so overselling checks compare against the *total* requested quantity.
    requested: dict[int, int] = defaultdict(int)
    for item in payload.items:
        requested[item.product_id] += item.quantity

    subtotal = 0
    products: dict[int, Product] = {}
    for product_id, quantity in requested.items():
        product = db.query(Product).options(joinedload(Product.category)).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(400, "Product not found.")
        if not product.available:
            raise HTTPException(400, f'"{product.name_display}" is disabled.')
        if not product.category.active:
            raise HTTPException(400, f'"{product.name_display}" is in a disabled category.')
        if product.stock <= 0:
            raise HTTPException(400, f'"{product.name_display}" is out of stock.')
        if product.stock < quantity:
            raise HTTPException(400, f'Only {product.stock} of "{product.name_display}" available.')
        products[product_id] = product
        subtotal += product.price * quantity

    discount = min(payload.discount, subtotal)
    taxable = subtotal - discount
    # Half-up rounding: (taxable * rate + 5000) // 10000
    tax = (taxable * payload.tax_rate + 5000) // 10000
    total = taxable + tax
    received = payload.amount_received

    if payload.payment_method == "CASH" and received < total:
        raise HTTPException(400, f"Cash received must be at least {total}.")
    change = received - total if payload.payment_method == "CASH" else 0

    # Nothing has been written yet: every validation above (bad product, insufficient
    # cash, closed table) fails before this point, so a failed/rejected order never
    # touches stock.
    #
    # order_number is derived from COUNT(*)+1, which is only a hint of the next
    # number, not a reservation: two concurrent requests can both read the same
    # count before either commits and both try to insert the same order_number.
    # SQLite's unique index then rejects the second INSERT with an IntegrityError
    # instead of silently allowing a duplicate, so this is a retry loop rather
    # than an extra correctness check — if two requests collide, the loser rolls
    # back and re-reads the count (now incremented by the winner's commit).
    order = None
    for _ in range(5):
        next_number = db.query(Order).count() + 1
        candidate = Order(
            order_number=f"ORD-{next_number:05d}",
            order_type=payload.order_type,
            table_id=payload.table_id,
            status="PAID",
            subtotal=subtotal,
            discount=discount,
            tax=tax,
            total=total,
            payment_method=payload.payment_method,
            amount_received=received,
            change_amount=change,
        )
        db.add(candidate)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        order = candidate
        break
    if order is None:
        raise HTTPException(409, "Could not create the order, please try again.")

    # Atomic, race-safe stock decrement. The WHERE clause re-checks stock at write
    # time (not just at the read above), so if two orders race for the last unit,
    # only one UPDATE can match `stock >= quantity` — the loser rolls back instead
    # of driving stock negative or double-selling the same item.
    #
    # Phase 5: each successful decrement also writes a SALE StockMovement, staged on
    # this same Session/transaction as the Order/OrderItem rows below and flushed by
    # the one db.commit() at the end — a payment that fails after this point (there
    # isn't one; nothing below can fail) can never leave stock decremented without a
    # matching movement, or vice versa. stock_before/after come from the row *after*
    # the atomic UPDATE (via refresh), not a separately-read value, so they're
    # correct even under concurrent writes to the same product.
    for product_id, quantity in requested.items():
        result = db.execute(
            update(Product)
            .where(Product.id == product_id, Product.stock >= quantity)
            .values(stock=Product.stock - quantity, updated_at=datetime.utcnow())
        )
        if result.rowcount == 0:
            db.rollback()
            product = db.get(Product, product_id)
            name = product.name_display if product else product_id
            available = product.stock if product else 0
            raise HTTPException(400, f'Only {available} of "{name}" available.')

        product = products[product_id]
        db.refresh(product)
        stock_after = product.stock
        stock_before = stock_after + quantity

        db.add(OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name=product.name_display,
            quantity=quantity,
            price=product.price,
            line_total=product.price * quantity,
        ))
        db.add(StockMovement(
            item_type="PRODUCT",
            item_id=product.id,
            item_name=product.name_display,
            movement_type="SALE",
            quantity_change=-quantity,
            reason="Sale",
            supplier=None,
            purchase_price=None,
            stock_before=stock_before,
            stock_after=stock_after,
            reference=order.order_number,
        ))

    db.commit()
    return db.query(Order).options(joinedload(Order.items)).filter(Order.id == order.id).first()


def cancel_order(db: Session, order_id: int, payload: OrderCancelIn) -> Order:
    """Phase 7–8: mark an order CANCELLED with a required reason, then restore its inventory.

    Phase 7: The order row is never deleted — only its status/cancellation fields change —
    and cancellation is a single atomic conditional UPDATE (WHERE status = 'PAID'), not a
    read-then-write, so two concurrent cancel requests for the same order can't both
    succeed: only the one that actually flips PAID -> CANCELLED wins, the other gets a
    clean 400 instead of double-cancelling.

    Phase 8: Inventory restoration (reversing the order's SALE StockMovements, identifiable
    via StockMovement.reference == order.order_number) now happens in the same transaction
    as the status change. The original SALE movements remain untouched; new CANCELLATION
    movements are created for the restored quantities. If the status change fails (order
    already cancelled or not found), the entire transaction is rolled back and no inventory
    is restored. If inventory restoration fails after the status change succeeded, the
    entire transaction is rolled back, so the order remains PAID.
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found.")

    label = CANCEL_REASON_LABELS[payload.reason]
    if payload.reason == "OTHER" and payload.note and payload.note.strip():
        label = f"Other: {payload.note.strip()}"

    result = db.execute(
        update(Order)
        .where(Order.id == order_id, Order.status == "PAID")
        .values(status="CANCELLED", cancelled_at=datetime.utcnow(), cancelled_reason=label)
    )
    if result.rowcount == 0:
        db.rollback()
        current = db.get(Order, order_id)
        if current and current.status == "CANCELLED":
            raise HTTPException(400, "This order has already been cancelled.")
        raise HTTPException(400, "Only a paid order can be cancelled.")

    # --- Phase 8: Inventory restoration, within the same transaction. ---
    # Find the original SALE movements for this order and restore each product's stock.
    sale_movements = db.query(StockMovement).filter(
        StockMovement.reference == order.order_number,
        StockMovement.movement_type == "SALE"
    ).all()

    for sale_movement in sale_movements:
        # Restore the quantity: undo the negative quantity_change from the SALE.
        restore_quantity = -sale_movement.quantity_change  # e.g., SALE was -2, restore is +2

        # For now, all movements are PRODUCT type. Get the product to update its stock.
        # Stage 6 will handle INGREDIENT type separately.
        if sale_movement.item_type == "PRODUCT":
            product = db.get(Product, sale_movement.item_id)
            # Atomic increment: update Product.stock by restore_quantity.
            db.execute(
                update(Product)
                .where(Product.id == product.id)
                .values(stock=Product.stock + restore_quantity, updated_at=datetime.utcnow())
            )

            # Refresh to get the new current stock value.
            db.refresh(product)
            stock_after = product.stock
            stock_before = stock_after - restore_quantity

            # Create a new CANCELLATION movement, referencing the same order.
            cancellation_movement = StockMovement(
                item_type=sale_movement.item_type,
                item_id=sale_movement.item_id,
                item_name=sale_movement.item_name,
                movement_type="CANCELLATION",
                quantity_change=restore_quantity,
                reason="Order cancellation",
                supplier=None,
                purchase_price=None,
                stock_before=stock_before,
                stock_after=stock_after,
                reference=order.order_number,
            )
            db.add(cancellation_movement)

    db.commit()
    return db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
