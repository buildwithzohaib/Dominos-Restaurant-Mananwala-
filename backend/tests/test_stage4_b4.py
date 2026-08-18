"""Tests for Stage 4, Task B4: pay_order() — take payment on open orders."""
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
    create_open_order, add_items_to_order, send_batch_to_kitchen, pay_order
)
from app.schemas.schemas import OpenOrderCreate, AddItemsIn, OrderItemCreate, PayOrderIn


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
        price=50000,  # 500 rupees
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
        price=60000,  # 600 rupees
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


def test_happy_path_open_add_send_pay(db: Session):
    """Happy path: open -> add -> send -> pay. Assert status == PAID, payment_method set, paid_at not None."""
    # Open
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    # Add items
    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),  # 50000 * 2 = 100000
    ])
    add_items_to_order(db, order_id, add_payload)

    # Send to kitchen
    send_batch_to_kitchen(db, order_id)

    # Pay
    pay_payload = PayOrderIn(
        payment_method="CASH",
        discount=0,
        amount_received=100000,
    )
    paid_order = pay_order(db, order_id, pay_payload)

    assert paid_order.status == "PAID"
    assert paid_order.payment_method == "CASH"
    assert paid_order.paid_at is not None


def test_stock_not_decremented_by_pay(db: Session):
    """Stock is NOT decremented again by paying, and NO new StockMovement is created."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)
    # Capture stock AFTER send_batch (when stock actually moves per Rule 8)
    prod = db.query(Product).filter(Product.id == db.prod1_id).first()
    stock_after_send = prod.stock
    movements_after_send = db.query(StockMovement).count()

    pay_payload = PayOrderIn(payment_method="CASH", amount_received=100000)
    pay_order(db, order_id, pay_payload)

    # Stock unchanged by pay_order
    db.refresh(prod)
    assert prod.stock == stock_after_send

    # No new StockMovement created by pay_order
    movements_after_pay = db.query(StockMovement).count()
    assert movements_after_pay == movements_after_send


def test_totals_with_tax_calculation(db: Session):
    """Totals with tax: known tax_rate, known items, assert subtotal, tax, total computed correctly."""
    settings = db.query(Settings).filter(Settings.id == 1).first()
    settings.tax_enabled = True
    settings.tax_rate = 1600  # 16%
    db.commit()

    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),  # 50000 * 2 = 100000
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)

    pay_payload = PayOrderIn(
        payment_method="CASH",
        discount=0,
        amount_received=116000,
    )
    paid_order = pay_order(db, order_id, pay_payload)

    # subtotal = 100000
    # tax = (100000 * 1600 + 5000) // 10000 = 160005000 // 10000 = 16000
    # total = 100000 + 16000 = 116000
    assert paid_order.subtotal == 100000
    assert paid_order.tax == 16000
    assert paid_order.total == 116000


def test_discount_is_applied(db: Session):
    """Discount is applied: assert taxable, tax and total all reflect it."""
    settings = db.query(Settings).filter(Settings.id == 1).first()
    settings.tax_enabled = True
    settings.tax_rate = 1000  # 10%
    db.commit()

    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),  # 50000 * 2 = 100000
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)

    # Apply 10000 paisa discount
    pay_payload = PayOrderIn(
        payment_method="CASH",
        discount=10000,
        amount_received=99000,
    )
    paid_order = pay_order(db, order_id, pay_payload)

    # subtotal = 100000
    # discount = 10000
    # taxable = 100000 - 10000 = 90000
    # tax = (90000 * 1000 + 5000) // 10000 = 90005000 // 10000 = 9000
    # total = 90000 + 9000 = 99000
    assert paid_order.subtotal == 100000
    assert paid_order.discount == 10000
    assert paid_order.tax == 9000
    assert paid_order.total == 99000
    assert paid_order.change_amount == 0


def test_discount_clamped_to_subtotal(db: Session):
    """Discount larger than subtotal is clamped to subtotal; total is never negative and tax is 0."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),  # 50000
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)

    # Try to apply discount larger than subtotal
    pay_payload = PayOrderIn(
        payment_method="CASH",
        discount=100000,  # More than subtotal (50000)
        amount_received=0,
    )
    paid_order = pay_order(db, order_id, pay_payload)

    # Discount is clamped to subtotal
    assert paid_order.subtotal == 50000
    assert paid_order.discount == 50000
    assert paid_order.tax == 0
    assert paid_order.total == 0


def test_tax_uses_order_snapshotted_rate_not_settings(db: Session):
    """Tax uses the ORDER's snapshotted tax_rate, not current settings."""
    settings = db.query(Settings).filter(Settings.id == 1).first()
    settings.tax_enabled = True
    settings.tax_rate = 1600  # 16%
    db.commit()

    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    # Verify order was opened with 16% tax
    assert order.tax_rate == 1600

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),  # 50000
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)

    # Now change settings to a different rate
    settings.tax_rate = 500  # 5%
    db.commit()

    # Pay the order
    pay_payload = PayOrderIn(
        payment_method="CASH",
        discount=0,
        amount_received=58000,
    )
    paid_order = pay_order(db, order_id, pay_payload)

    # Tax should use the original 16%, not the new 5%
    # tax = (50000 * 1600 + 5000) // 10000 = 80005000 // 10000 = 8000
    # total = 50000 + 8000 = 58000
    assert paid_order.tax_rate == 1600
    assert paid_order.tax == 8000
    assert paid_order.total == 58000


def test_cash_insufficient_amount_rejected(db: Session):
    """CASH with amount_received < total -> 400, order still OPEN with paid_at None."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),  # 100000
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)

    # Try to pay with insufficient cash
    pay_payload = PayOrderIn(
        payment_method="CASH",
        discount=0,
        amount_received=50000,  # Less than 100000
    )

    with pytest.raises(HTTPException) as exc_info:
        pay_order(db, order_id, pay_payload)

    assert exc_info.value.status_code == 400
    assert "Cash received must be at least" in exc_info.value.detail

    # Verify order is still OPEN and paid_at is None
    order_after = db.query(Order).filter(Order.id == order_id).first()
    assert order_after.status == "OPEN"
    assert order_after.paid_at is None


def test_cash_exact_amount_change_is_zero(db: Session):
    """CASH with exact amount -> change_amount == 0."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),  # 100000
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)

    pay_payload = PayOrderIn(
        payment_method="CASH",
        discount=0,
        amount_received=100000,
    )
    paid_order = pay_order(db, order_id, pay_payload)

    assert paid_order.change_amount == 0


def test_cash_more_than_total_change_calculated(db: Session):
    """CASH with more than total -> change_amount == the difference."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),  # 100000
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)

    pay_payload = PayOrderIn(
        payment_method="CASH",
        discount=0,
        amount_received=150000,
    )
    paid_order = pay_order(db, order_id, pay_payload)

    assert paid_order.change_amount == 50000


def test_card_payment_change_is_zero(db: Session):
    """CARD -> change_amount == 0."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),  # 50000
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)

    pay_payload = PayOrderIn(
        payment_method="CARD",
        discount=0,
        amount_received=75000,  # Random amount, doesn't matter for CARD
    )
    paid_order = pay_order(db, order_id, pay_payload)

    assert paid_order.change_amount == 0
    assert paid_order.payment_method == "CARD"


def test_other_payment_change_is_zero(db: Session):
    """OTHER -> change_amount == 0."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),  # 50000
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)

    pay_payload = PayOrderIn(
        payment_method="OTHER",
        discount=0,
        amount_received=123456,  # Random amount
    )
    paid_order = pay_order(db, order_id, pay_payload)

    assert paid_order.change_amount == 0
    assert paid_order.payment_method == "OTHER"


def test_pending_items_reject_payment(db: Session):
    """Paying an order that still has a PENDING item -> 400, order still OPEN."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    add_items_to_order(db, order_id, add_payload)

    # Do NOT send to kitchen, leave items PENDING

    pay_payload = PayOrderIn(
        payment_method="CASH",
        discount=0,
        amount_received=100000,
    )

    with pytest.raises(HTTPException) as exc_info:
        pay_order(db, order_id, pay_payload)

    assert exc_info.value.status_code == 400
    assert "Send all items to the kitchen" in exc_info.value.detail

    # Verify order still OPEN
    order_after = db.query(Order).filter(Order.id == order_id).first()
    assert order_after.status == "OPEN"


def test_no_items_reject_payment(db: Session):
    """Paying an order with no items at all -> 400."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    # No items added

    pay_payload = PayOrderIn(
        payment_method="CASH",
        discount=0,
        amount_received=0,
    )

    with pytest.raises(HTTPException) as exc_info:
        pay_order(db, order_id, pay_payload)

    assert exc_info.value.status_code == 400
    assert "no items" in exc_info.value.detail


def test_already_paid_order_reject(db: Session):
    """Paying an already PAID order -> 400."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)

    pay_payload = PayOrderIn(
        payment_method="CASH",
        discount=0,
        amount_received=50000,
    )
    pay_order(db, order_id, pay_payload)

    # Try to pay again
    with pytest.raises(HTTPException) as exc_info:
        pay_order(db, order_id, pay_payload)

    assert exc_info.value.status_code == 400
    assert "open order" in exc_info.value.detail


def test_cancelled_order_reject(db: Session):
    """Paying a CANCELLED order -> 400."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),
    ])
    add_items_to_order(db, order_id, add_payload)

    # Mark as CANCELLED
    order.status = "CANCELLED"
    db.commit()

    pay_payload = PayOrderIn(
        payment_method="CASH",
        discount=0,
        amount_received=50000,
    )

    with pytest.raises(HTTPException) as exc_info:
        pay_order(db, order_id, pay_payload)

    assert exc_info.value.status_code == 400
    assert "open order" in exc_info.value.detail


def test_nonexistent_order_reject(db: Session):
    """Paying a nonexistent order_id -> 404."""
    pay_payload = PayOrderIn(
        payment_method="CASH",
        discount=0,
        amount_received=50000,
    )

    with pytest.raises(HTTPException) as exc_info:
        pay_order(db, 999, pay_payload)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail


def test_table_free_after_payment(db: Session):
    """After payment the table is free: a new create_open_order on the same table succeeds."""
    # First order
    create_payload1 = OpenOrderCreate(table_id=db.table_a_id)
    order1 = create_open_order(db, create_payload1)
    order1_id = order1.id

    add_payload1 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),
    ])
    add_items_to_order(db, order1_id, add_payload1)

    send_batch_to_kitchen(db, order1_id)

    pay_payload = PayOrderIn(
        payment_method="CASH",
        discount=0,
        amount_received=50000,
    )
    pay_order(db, order1_id, pay_payload)

    # Now open a new order on the same table (should succeed)
    create_payload2 = OpenOrderCreate(table_id=db.table_a_id)
    order2 = create_open_order(db, create_payload2)

    assert order2.status == "OPEN"
    assert order2.table_id == db.table_a_id
    assert order2.id != order1_id
