"""Tests for Stage 4, Task B1: create_open_order() — running-tab dine-in orders."""
import gc
import os
import tempfile
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi import HTTPException

from app.database import Base
from app.models.models import (
    Order, OrderItem, Product, Category, Customer, RestaurantTable, Settings, StockMovement
)
from app.services.order_service import create_open_order
from app.schemas.schemas import OpenOrderCreate


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
        min_stock=5,
        unit="Portion",
        available=True,
    )
    session.add(prod1)
    session.flush()

    # Seed tables (names do NOT contain their ids)
    table_a = RestaurantTable(id=7, name="Patio A", seats=2, active=True)
    table_b = RestaurantTable(id=8, name="Corner Booth", seats=4, active=True)
    table_closed = RestaurantTable(id=9, name="Garden Side", seats=2, active=False)
    session.add_all([table_a, table_b, table_closed])
    session.flush()

    # Seed customers
    cust_active = Customer(
        name_raw="Ali",
        name_display="Ali",
        name_key="ali",
        phone_raw="03001234567",
        phone_key="03001234567",
        is_active=True
    )
    cust_inactive = Customer(
        name_raw="Zara",
        name_display="Zara",
        name_key="zara",
        phone_raw="03009876543",
        phone_key="03009876543",
        is_active=False
    )
    session.add_all([cust_active, cust_inactive])
    session.commit()

    # Expose seeded ids to tests
    session.table_a_id = table_a.id
    session.table_b_id = table_b.id
    session.table_closed_id = table_closed.id
    session.cust_active_id = cust_active.id
    session.cust_inactive_id = cust_inactive.id

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


def test_create_open_order_success(db: Session):
    """Create an OPEN order on an active table."""
    payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, payload)

    assert order.status == "OPEN"
    assert order.table_id == db.table_a_id
    assert order.order_type == "DINE_IN"
    assert order.payment_method is None
    assert order.subtotal == 0
    assert order.discount == 0
    assert order.tax == 0
    assert order.total == 0
    assert order.amount_received == 0
    assert order.change_amount == 0
    assert len(order.items) == 0
    assert order.order_number.startswith("ORD-")


def test_open_order_payment_method_is_none_not_empty_string(db: Session):
    """payment_method must be NULL, never empty string."""
    payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, payload)

    assert order.payment_method is None


def test_open_order_snapshots_tax_rate_from_settings_enabled(db: Session):
    """tax_rate is snapshotted from settings at open time."""
    settings = db.query(Settings).filter(Settings.id == 1).first()
    settings.tax_enabled = True
    settings.tax_rate = 1600  # 16%
    db.commit()

    payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, payload)

    assert order.tax_rate == 1600


def test_open_order_tax_rate_zero_when_disabled(db: Session):
    """tax_rate is 0 when settings.tax_enabled is False."""
    settings = db.query(Settings).filter(Settings.id == 1).first()
    settings.tax_enabled = False
    settings.tax_rate = 1600  # Should be ignored
    db.commit()

    payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, payload)

    assert order.tax_rate == 0


def test_open_order_no_stock_deduction(db: Session):
    """Stock should not be deducted for OPEN orders."""
    prod = db.query(Product).first()
    stock_before = prod.stock

    payload = OpenOrderCreate(table_id=db.table_a_id)
    create_open_order(db, payload)

    db.refresh(prod)
    assert prod.stock == stock_before


def test_open_order_no_stock_movements(db: Session):
    """No SALE movements should be created for OPEN orders."""
    payload = OpenOrderCreate(table_id=db.table_a_id)
    create_open_order(db, payload)

    movements = db.query(StockMovement).all()
    assert len(movements) == 0


def test_reject_second_open_order_same_table(db: Session):
    """Second OPEN order on the same table raises 400 with table name, not id."""
    payload = OpenOrderCreate(table_id=db.table_a_id)
    order1 = create_open_order(db, payload)

    with pytest.raises(HTTPException) as exc_info:
        create_open_order(db, payload)

    detail = exc_info.value.detail
    assert exc_info.value.status_code == 400
    assert "Patio A" in detail
    assert "7" not in detail


def test_open_order_different_table_succeeds(db: Session):
    """OPEN orders on different tables should both succeed."""
    payload_a = OpenOrderCreate(table_id=db.table_a_id)
    payload_b = OpenOrderCreate(table_id=db.table_b_id)

    order_a = create_open_order(db, payload_a)
    order_b = create_open_order(db, payload_b)

    assert order_a.table_id == db.table_a_id
    assert order_b.table_id == db.table_b_id
    assert order_a.status == "OPEN"
    assert order_b.status == "OPEN"


def test_reject_inactive_table(db: Session):
    """Inactive table raises 400."""
    payload = OpenOrderCreate(table_id=db.table_closed_id)

    with pytest.raises(HTTPException) as exc_info:
        create_open_order(db, payload)

    assert exc_info.value.status_code == 400
    assert "not available" in exc_info.value.detail


def test_reject_nonexistent_table(db: Session):
    """Non-existent table_id raises 400."""
    payload = OpenOrderCreate(table_id=999)

    with pytest.raises(HTTPException) as exc_info:
        create_open_order(db, payload)

    assert exc_info.value.status_code == 400
    assert "not available" in exc_info.value.detail


def test_reject_inactive_customer(db: Session):
    """Inactive customer raises 400."""
    payload = OpenOrderCreate(table_id=db.table_a_id, customer_id=db.cust_inactive_id)

    with pytest.raises(HTTPException) as exc_info:
        create_open_order(db, payload)

    assert exc_info.value.status_code == 400
    assert "inactive" in exc_info.value.detail


def test_reject_nonexistent_customer(db: Session):
    """Non-existent customer_id raises 404."""
    payload = OpenOrderCreate(table_id=db.table_a_id, customer_id=999)

    with pytest.raises(HTTPException) as exc_info:
        create_open_order(db, payload)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail


def test_open_order_with_valid_customer(db: Session):
    """Open order with a valid customer succeeds."""
    payload = OpenOrderCreate(table_id=db.table_a_id, customer_id=db.cust_active_id)
    order = create_open_order(db, payload)

    assert order.customer_id == db.cust_active_id
    assert order.status == "OPEN"


def test_open_order_after_previous_paid(db: Session):
    """After first order is PAID, same table can have new OPEN order."""
    payload1 = OpenOrderCreate(table_id=db.table_a_id)
    order1 = create_open_order(db, payload1)

    order1.status = "PAID"
    order1.payment_method = "CASH"
    db.commit()

    payload2 = OpenOrderCreate(table_id=db.table_a_id)
    order2 = create_open_order(db, payload2)

    assert order2.table_id == db.table_a_id
    assert order2.status == "OPEN"
    assert order2.id != order1.id


def test_order_number_format(db: Session):
    """Order number follows ORD-NNNNN format."""
    payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, payload)

    assert order.order_number.startswith("ORD-")
    parts = order.order_number.split("-")
    assert len(parts) == 2
    assert parts[1].isdigit()
    assert len(parts[1]) == 5
