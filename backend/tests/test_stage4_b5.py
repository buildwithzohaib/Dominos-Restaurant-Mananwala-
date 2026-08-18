"""Tests for Stage 4, Task B5: cancel_order() updated to handle OPEN orders."""
import gc
import os
import tempfile
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi import HTTPException

from app.database import Base
from app.models.models import Order, OrderItem, Product, Category, RestaurantTable, Settings, StockMovement
from app.services.order_service import (
    create_open_order, add_items_to_order, send_batch_to_kitchen, pay_order, cancel_order
)
from app.schemas.schemas import OpenOrderCreate, AddItemsIn, OrderItemCreate, PayOrderIn, OrderCancelIn


@pytest.fixture(scope="function")
def db() -> Session:
    """Create a temporary SQLite database for each test."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Seed settings
    settings = Settings()
    session.add(settings)

    # Seed categories
    cat1 = Category(name_raw="Biryani", name_display="Biryani", name_key="biryani", active=True)
    session.add(cat1)
    session.flush()

    # Seed products
    prod1 = Product(
        category_id=cat1.id,
        name_raw="Chicken Biryani",
        name_display="Chicken Biryani",
        name_key="chickenbiryani",
        price=50000,
        stock=100,
        sku="BIRYANI-001",
        min_stock=1,
        unit="Portion",
        available=True,
    )
    prod2 = Product(
        category_id=cat1.id,
        name_raw="Lamb Karahi",
        name_display="Lamb Karahi",
        name_key="lambkarahi",
        price=60000,
        stock=100,
        sku="KARAHI-001",
        min_stock=1,
        unit="Portion",
        available=True,
    )
    session.add_all([prod1, prod2])
    session.flush()

    # Seed tables
    table_a = RestaurantTable(id=7, name="Patio A", seats=2, active=True)
    table_b = RestaurantTable(id=8, name="Corner Booth", seats=4, active=True)
    session.add_all([table_a, table_b])
    session.commit()

    # Expose seeded ids to tests
    session.table_a_id = table_a.id
    session.table_b_id = table_b.id
    session.prod1_id = prod1.id
    session.prod2_id = prod2.id

    yield session

    session.close()
    engine.dispose()
    gc.collect()
    time.sleep(0.1)

    for _ in range(5):
        try:
            os.remove(db_path)
            break
        except OSError:
            time.sleep(0.1)


def test_cancel_open_order_pending_items_only(db: Session):
    """Cancelling an OPEN order with only PENDING items: status CANCELLED, stock unchanged, no CANCELLATION movement."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    prod = db.query(Product).filter(Product.id == db.prod1_id).first()
    stock_before = prod.stock

    # Add items but do NOT send to kitchen (items remain PENDING)
    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    add_items_to_order(db, order_id, add_payload)

    # Cancel the order
    cancel_payload = OrderCancelIn(reason="CUSTOMER_CHANGED_ORDER")
    cancelled_order = cancel_order(db, order_id, cancel_payload)

    assert cancelled_order.status == "CANCELLED"

    # Stock unchanged (no SALE movements were created for PENDING items)
    db.refresh(prod)
    assert prod.stock == stock_before

    # No CANCELLATION movements created
    movements = db.query(StockMovement).all()
    assert len(movements) == 0


def test_cancel_open_order_all_sent_items(db: Session):
    """Cancelling an OPEN order with all items sent: stock restored, CANCELLATION movements created."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    prod = db.query(Product).filter(Product.id == db.prod1_id).first()
    stock_before = prod.stock  # 100

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=3),
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)

    # Cancel the order
    cancel_payload = OrderCancelIn(reason="CUSTOMER_CHANGED_ORDER")
    cancelled_order = cancel_order(db, order_id, cancel_payload)

    assert cancelled_order.status == "CANCELLED"

    # Stock restored
    db.refresh(prod)
    assert prod.stock == stock_before  # 100

    # One SALE movement and one CANCELLATION movement
    movements = db.query(StockMovement).filter(
        StockMovement.reference == order.order_number
    ).all()
    assert len(movements) == 2
    sale = next(m for m in movements if m.movement_type == "SALE")
    cancellation = next(m for m in movements if m.movement_type == "CANCELLATION")
    assert sale.quantity_change == -3
    assert cancellation.quantity_change == 3


def test_cancel_open_order_mixed_sent_and_pending(db: Session):
    """Mixed case: some items sent, some pending. Only sent quantities are restored."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    prod = db.query(Product).filter(Product.id == db.prod1_id).first()
    stock_before = prod.stock  # 100

    # Add 3 items and send all as batch 1
    add_payload1 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=3),
    ])
    add_items_to_order(db, order_id, add_payload1)
    send_batch_to_kitchen(db, order_id)

    # Add 2 more items and leave them pending (not sent)
    add_payload2 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    add_items_to_order(db, order_id, add_payload2)

    # Now we have: 3 items sent in batch 1, 2 items pending. Cancelling must restore only the 3 sent.
    cancel_payload = OrderCancelIn(reason="CUSTOMER_CHANGED_ORDER")
    cancelled_order = cancel_order(db, order_id, cancel_payload)

    assert cancelled_order.status == "CANCELLED"

    # Only the 3 sent items are restored, back to the original 100
    db.refresh(prod)
    assert prod.stock == stock_before  # 100

    # One SALE movement for the 3 sent items, one CANCELLATION
    movements = db.query(StockMovement).filter(
        StockMovement.reference == order.order_number
    ).all()
    assert len(movements) == 2
    sale = next(m for m in movements if m.movement_type == "SALE")
    cancellation = next(m for m in movements if m.movement_type == "CANCELLATION")
    assert sale.quantity_change == -3
    assert cancellation.quantity_change == 3


def test_original_sale_movements_remain_after_cancel(db: Session):
    """The original SALE movements are still present after cancelling (append-only ledger)."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)
    sale_movement_count = db.query(StockMovement).filter(
        StockMovement.movement_type == "SALE"
    ).count()

    cancel_payload = OrderCancelIn(reason="CUSTOMER_CHANGED_ORDER")
    cancel_order(db, order_id, cancel_payload)

    # Original SALE movement still exists
    assert db.query(StockMovement).filter(
        StockMovement.movement_type == "SALE"
    ).count() == sale_movement_count

    # CANCELLATION movement added
    assert db.query(StockMovement).filter(
        StockMovement.movement_type == "CANCELLATION"
    ).count() == 1


def test_table_free_after_cancelling_open_order(db: Session):
    """Cancelling an OPEN order frees the table: create_open_order succeeds."""
    create_payload1 = OpenOrderCreate(table_id=db.table_a_id)
    order1 = create_open_order(db, create_payload1)

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),
    ])
    add_items_to_order(db, order1.id, add_payload)

    cancel_payload = OrderCancelIn(reason="CUSTOMER_CHANGED_ORDER")
    cancel_order(db, order1.id, cancel_payload)

    # Now open a new order on the same table
    create_payload2 = OpenOrderCreate(table_id=db.table_a_id)
    order2 = create_open_order(db, create_payload2)

    assert order2.status == "OPEN"
    assert order2.table_id == db.table_a_id


def test_cancel_paid_order_regression(db: Session):
    """Cancelling a PAID order still works exactly as before (regression check)."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    prod = db.query(Product).filter(Product.id == db.prod1_id).first()
    stock_before = prod.stock

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)

    pay_payload = PayOrderIn(payment_method="CASH", amount_received=100000)
    pay_order(db, order_id, pay_payload)

    # Now cancel the PAID order
    cancel_payload = OrderCancelIn(reason="CUSTOMER_CHANGED_ORDER")
    cancelled_order = cancel_order(db, order_id, cancel_payload)

    assert cancelled_order.status == "CANCELLED"

    # Stock restored
    db.refresh(prod)
    assert prod.stock == stock_before


def test_cancel_already_cancelled_order(db: Session):
    """Cancelling an already CANCELLED order -> 400 with "already been cancelled" message."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    cancel_payload = OrderCancelIn(reason="CUSTOMER_CHANGED_ORDER")
    cancel_order(db, order_id, cancel_payload)

    # Try to cancel again
    with pytest.raises(HTTPException) as exc_info:
        cancel_order(db, order_id, cancel_payload)

    assert exc_info.value.status_code == 400
    assert "already been cancelled" in exc_info.value.detail


def test_cancel_nonexistent_order(db: Session):
    """Cancelling a nonexistent order -> 404."""
    cancel_payload = OrderCancelIn(reason="CUSTOMER_CHANGED_ORDER")

    with pytest.raises(HTTPException) as exc_info:
        cancel_order(db, 999, cancel_payload)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail


def test_cancelled_at_and_reason_set(db: Session):
    """cancelled_at and cancelled_reason are set, and the reason label matches CANCEL_REASON_LABELS."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    cancel_payload = OrderCancelIn(reason="WRONG_ORDER")
    cancelled_order = cancel_order(db, order_id, cancel_payload)

    assert cancelled_order.cancelled_at is not None
    assert cancelled_order.cancelled_reason == "Wrong order"


def test_reason_other_with_note(db: Session):
    """Reason 'OTHER' with a note produces the 'Other: <note>' label."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    cancel_payload = OrderCancelIn(reason="OTHER", note="Customer felt sick")
    cancelled_order = cancel_order(db, order_id, cancel_payload)

    assert cancelled_order.cancelled_reason == "Other: Customer felt sick"


def test_cancelled_open_order_paid_at_remains_null(db: Session):
    """A cancelled OPEN order keeps paid_at NULL."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),
    ])
    add_items_to_order(db, order_id, add_payload)

    cancel_payload = OrderCancelIn(reason="CUSTOMER_CHANGED_ORDER")
    cancelled_order = cancel_order(db, order_id, cancel_payload)

    assert cancelled_order.paid_at is None


def test_order_row_exists_after_cancel(db: Session):
    """The order row still exists after cancelling (nothing hard-deleted)."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    cancel_payload = OrderCancelIn(reason="CUSTOMER_CHANGED_ORDER")
    cancel_order(db, order_id, cancel_payload)

    # Query should find the order
    order_after = db.query(Order).filter(Order.id == order_id).first()
    assert order_after is not None
    assert order_after.status == "CANCELLED"
