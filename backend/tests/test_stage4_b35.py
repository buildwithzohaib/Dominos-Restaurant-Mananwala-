"""Tests for Stage 4, Task B3.5: paid_at column — track payment timestamp."""
import gc
import os
import tempfile
import time
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.database import Base
from app.models.models import Order, Product, Category, RestaurantTable, Settings
from app.services.order_service import create_open_order, add_items_to_order, send_batch_to_kitchen, create_order
from app.schemas.schemas import OpenOrderCreate, AddItemsIn, OrderItemCreate, OrderCreate


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
    session.add(prod1)
    session.flush()

    # Seed tables
    table_a = RestaurantTable(id=7, name="Patio A", seats=2, active=True)
    session.add(table_a)
    session.commit()

    # Expose seeded ids to tests
    session.table_a_id = table_a.id
    session.prod1_id = prod1.id

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


def test_open_order_has_paid_at_none(db: Session):
    """A newly opened order (create_open_order) has paid_at IS None."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)

    assert order.paid_at is None


def test_paid_at_still_none_after_add_items(db: Session):
    """paid_at is still None after add_items_to_order."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    updated_order = add_items_to_order(db, order_id, add_payload)

    assert updated_order.paid_at is None


def test_paid_at_still_none_after_send_batch(db: Session):
    """paid_at is still None after send_batch_to_kitchen."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    add_items_to_order(db, order_id, add_payload)

    sent_order = send_batch_to_kitchen(db, order_id)

    assert sent_order.paid_at is None


def test_create_order_has_non_null_paid_at(db: Session):
    """An order created via create_order (which is PAID immediately) has a non-null paid_at."""
    order_payload = OrderCreate(
        order_type="TAKEAWAY",
        items=[
            OrderItemCreate(product_id=db.prod1_id, quantity=1),
        ],
        payment_method="CASH",
        amount_received=50000,
    )
    order = create_order(db, order_payload)

    assert order.paid_at is not None


def test_create_order_paid_at_within_second_of_created_at(db: Session):
    """For a create_order order, paid_at and created_at are within a second of each other."""
    before = datetime.utcnow()
    order_payload = OrderCreate(
        order_type="TAKEAWAY",
        items=[
            OrderItemCreate(product_id=db.prod1_id, quantity=1),
        ],
        payment_method="CASH",
        amount_received=50000,
    )
    order = create_order(db, order_payload)
    after = datetime.utcnow()

    # Both created_at and paid_at should be within the before/after window
    assert before <= order.created_at <= after
    assert before <= order.paid_at <= after
    # They should be very close (within 1 second of each other)
    assert abs((order.paid_at - order.created_at).total_seconds()) < 1
