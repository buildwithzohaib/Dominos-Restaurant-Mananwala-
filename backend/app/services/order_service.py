from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

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

TWOPLACES = Decimal("0.01")
def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

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

    subtotal = Decimal("0")
    products: dict[int, Product] = {}
    for product_id, quantity in requested.items():
        product = db.get(Product, product_id)
        if not product or not product.available:
            raise HTTPException(400, f"Product {product_id} is unavailable.")
        if product.stock <= 0:
            raise HTTPException(400, f'"{product.name}" is out of stock.')
        if product.stock < quantity:
            raise HTTPException(400, f'Only {product.stock} of "{product.name}" available.')
        products[product_id] = product
        subtotal += Decimal(product.price) * quantity

    subtotal = money(subtotal)
    discount = min(money(payload.discount), subtotal)
    taxable = subtotal - discount
    tax = money(taxable * payload.tax_rate / Decimal("100"))
    total = money(taxable + tax)
    received = money(payload.amount_received)

    if payload.payment_method == "CASH" and received < total:
        raise HTTPException(400, f"Cash received must be at least {total}.")
    change = money(received - total) if payload.payment_method == "CASH" else Decimal("0")

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
            name = product.name if product else product_id
            available = product.stock if product else 0
            raise HTTPException(400, f'Only {available} of "{name}" available.')

        product = products[product_id]
        db.refresh(product)
        stock_after = product.stock
        stock_before = stock_after + quantity

        db.add(OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name=product.name,
            quantity=quantity,
            price=money(Decimal(product.price)),
            line_total=money(Decimal(product.price) * quantity),
        ))
        db.add(StockMovement(
            product_id=product.id,
            product_name=product.name,
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
    """Phase 7: mark an order CANCELLED with a required reason. The order row is
    never deleted — only its status/cancellation fields change — and cancellation
    is a single atomic conditional UPDATE (WHERE status = 'PAID'), not a
    read-then-write, so two concurrent cancel requests for the same order can't
    both succeed: only the one that actually flips PAID -> CANCELLED wins, the
    other gets a clean 400 instead of double-cancelling.

    Phase 8 hook: inventory restoration (reversing the order's SALE StockMovements,
    identifiable via StockMovement.reference == order.order_number) belongs right
    here, before the commit below, so it lands in the same transaction as the
    status change. Deliberately not implemented yet — see Phase 7 §15.
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

    # --- Phase 8 hook goes here (inventory restoration), before this commit. ---

    db.commit()
    return db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
