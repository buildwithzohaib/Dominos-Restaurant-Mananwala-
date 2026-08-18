"""Tests for Stage 4, Task B3: send_batch_to_kitchen() — send items to kitchen and decrement stock."""
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
from app.services.order_service import create_open_order, add_items_to_order, send_batch_to_kitchen
from app.schemas.schemas import OpenOrderCreate, AddItemsIn, OrderItemCreate


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

    # Seed products with small, known stock levels for easy failure testing
    prod1 = Product(
        category_id=cat1.id,
        name_raw="Chicken Biryani",
        name_display="Chicken Biryani",
        name_key="chickenbiryani",
        price=50000,
        stock=5,  # Small stock for testing
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
        stock=3,  # Small stock
        sku="KARAHI-001",
        min_stock=1,
        unit="Portion",
        available=True,
    )
    prod_low_stock = Product(
        category_id=cat1.id,
        name_raw="Palak Paneer",
        name_display="Palak Paneer",
        name_key="palakpaneer",
        price=40000,
        stock=1,  # Very low stock
        sku="PANEER-001",
        min_stock=1,
        unit="Portion",
        available=True,
    )
    session.add_all([prod1, prod2, prod_low_stock])
    session.flush()

    # Seed tables
    table_a = RestaurantTable(id=7, name="Patio A", seats=2, active=True)
    table_b = RestaurantTable(id=8, name="Corner Booth", seats=4, active=True)
    session.add_all([table_a, table_b])
    session.flush()

    # Seed customer
    cust_active = Customer(
        name_raw="Ali",
        name_display="Ali",
        name_key="ali",
        phone_raw="03001234567",
        phone_key="03001234567",
        is_active=True
    )
    session.add(cust_active)
    session.commit()

    # Expose seeded ids to tests
    session.table_a_id = table_a.id
    session.table_b_id = table_b.id
    session.prod1_id = prod1.id
    session.prod2_id = prod2.id
    session.prod_low_stock_id = prod_low_stock.id

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


def test_send_batch_stamps_items_with_batch_id_and_sent_at(db: Session):
    """Sending a batch stamps every pending item with batch_id = 1 and a non-null sent_at."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    add_items_to_order(db, order_id, add_payload)

    # Send batch
    sent_order = send_batch_to_kitchen(db, order_id)

    assert len(sent_order.items) == 1
    assert sent_order.items[0].batch_id == 1
    assert sent_order.items[0].sent_at is not None


def test_send_batch_decrements_stock(db: Session):
    """Stock IS decremented by the sent quantity."""
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

    db.refresh(prod)
    assert prod.stock == stock_before - 2


def test_send_batch_creates_stock_movement(db: Session):
    """Exactly one SALE StockMovement per product with correct values."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)

    movements = db.query(StockMovement).all()
    assert len(movements) == 1
    movement = movements[0]
    assert movement.movement_type == "SALE"
    assert movement.quantity_change == -2
    assert movement.reference == order.order_number
    assert movement.item_type == "PRODUCT"
    assert movement.item_id == db.prod1_id
    assert movement.reason == "Sale"
    assert movement.supplier is None
    assert movement.purchase_price is None


def test_stock_movement_before_after_values(db: Session):
    """Stock movement has correct stock_before/stock_after values."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    prod = db.query(Product).filter(Product.id == db.prod1_id).first()
    initial_stock = prod.stock  # 5

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    add_items_to_order(db, order_id, add_payload)

    send_batch_to_kitchen(db, order_id)

    movement = db.query(StockMovement).first()
    assert movement.stock_before == initial_stock  # 5
    assert movement.stock_after == initial_stock - 2  # 3


def test_second_send_produces_batch_id_2_does_not_resend_batch_1(db: Session):
    """Second send produces batch_id = 2, does NOT re-send or re-charge batch 1."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    prod = db.query(Product).filter(Product.id == db.prod1_id).first()
    initial_stock = prod.stock  # 5

    # First send
    add_payload1 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    add_items_to_order(db, order_id, add_payload1)
    order_after_first = send_batch_to_kitchen(db, order_id)

    # Check first batch
    assert len(order_after_first.items) == 1
    assert order_after_first.items[0].batch_id == 1
    db.refresh(prod)
    assert prod.stock == initial_stock - 2  # 3

    # Second send
    add_payload2 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),
    ])
    add_items_to_order(db, order_id, add_payload2)
    order_after_second = send_batch_to_kitchen(db, order_id)

    # Check second batch
    assert len(order_after_second.items) == 2
    batch_1_item = next(item for item in order_after_second.items if item.batch_id == 1)
    batch_2_item = next(item for item in order_after_second.items if item.batch_id == 2)
    assert batch_1_item.quantity == 2
    assert batch_2_item.quantity == 1

    # Stock decremented only once more
    db.refresh(prod)
    assert prod.stock == initial_stock - 3  # 2


def test_batch_numbering_per_order(db: Session):
    """Batch numbering is per-order: two different orders each start at batch 1."""
    # Order 1
    create_payload1 = OpenOrderCreate(table_id=db.table_a_id)
    order1 = create_open_order(db, create_payload1)
    add_payload1 = AddItemsIn(items=[OrderItemCreate(product_id=db.prod1_id, quantity=1)])
    add_items_to_order(db, order1.id, add_payload1)
    order1_sent = send_batch_to_kitchen(db, order1.id)

    # Order 2
    create_payload2 = OpenOrderCreate(table_id=db.table_b_id)
    order2 = create_open_order(db, create_payload2)
    add_payload2 = AddItemsIn(items=[OrderItemCreate(product_id=db.prod2_id, quantity=1)])
    add_items_to_order(db, order2.id, add_payload2)
    order2_sent = send_batch_to_kitchen(db, order2.id)

    # Both start at batch 1
    assert order1_sent.items[0].batch_id == 1
    assert order2_sent.items[0].batch_id == 1


def test_items_keep_original_batch_id_after_later_send(db: Session):
    """Items already sent keep their original batch_id and sent_at after a later send."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    # First send
    add_payload1 = AddItemsIn(items=[OrderItemCreate(product_id=db.prod1_id, quantity=1)])
    add_items_to_order(db, order_id, add_payload1)
    order_after_first = send_batch_to_kitchen(db, order_id)
    batch1_item = order_after_first.items[0]
    batch1_sent_at = batch1_item.sent_at

    # Second send
    add_payload2 = AddItemsIn(items=[OrderItemCreate(product_id=db.prod2_id, quantity=1)])
    add_items_to_order(db, order_id, add_payload2)
    order_after_second = send_batch_to_kitchen(db, order_id)

    # Find batch 1 item again
    batch1_item_after = next(item for item in order_after_second.items if item.batch_id == 1)
    assert batch1_item_after.batch_id == 1
    assert batch1_item_after.sent_at == batch1_sent_at


def test_send_with_no_pending_items_rejected(db: Session):
    """Sending when there are no pending items -> 400."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    with pytest.raises(HTTPException) as exc_info:
        send_batch_to_kitchen(db, order_id)

    assert exc_info.value.status_code == 400
    assert "no new items" in exc_info.value.detail


def test_send_when_pending_items_exceed_stock_rejected_with_rollback(db: Session):
    """Pending items exceed current stock -> 400, with full rollback (no item stamped, no movement, stock unchanged)."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    prod = db.query(Product).filter(Product.id == db.prod_low_stock_id).first()
    initial_stock = prod.stock  # 1

    # Add 1 item (passes add-time check)
    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod_low_stock_id, quantity=1),
    ])
    add_items_to_order(db, order_id, add_payload)

    # Reduce stock directly (simulating another table consuming it)
    prod.stock = 0
    db.commit()

    # Send should now fail
    with pytest.raises(HTTPException) as exc_info:
        send_batch_to_kitchen(db, order_id)

    assert exc_info.value.status_code == 400
    assert "Only 0" in exc_info.value.detail

    # Verify rollback: item not stamped
    order_after = db.query(Order).filter(Order.id == order_id).first()
    assert order_after.items[0].batch_id is None
    assert order_after.items[0].sent_at is None

    # Verify rollback: no StockMovement created
    movements = db.query(StockMovement).all()
    assert len(movements) == 0

    # Verify rollback: stock is still 0 (what we set it to)
    db.refresh(prod)
    assert prod.stock == 0


def test_all_or_nothing_two_products_one_fits_one_does_not(db: Session):
    """ALL-OR-NOTHING with TWO products: one fits, one does not -> 400, product that would fit NOT decremented."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    prod1 = db.query(Product).filter(Product.id == db.prod1_id).first()
    prod2 = db.query(Product).filter(Product.id == db.prod2_id).first()
    prod1_stock_before = prod1.stock  # 5
    prod2_stock_before = prod2.stock  # 3

    # Add items: prod1 has enough (5 >= 2), prod2 has enough at add time (3 >= 3)
    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
        OrderItemCreate(product_id=db.prod2_id, quantity=3),
    ])
    add_items_to_order(db, order_id, add_payload)

    # Reduce prod2's stock directly (simulating another table consuming it)
    prod2.stock = 1
    db.commit()

    # Send should fail (prod2 doesn't have enough anymore)
    with pytest.raises(HTTPException) as exc_info:
        send_batch_to_kitchen(db, order_id)

    assert exc_info.value.status_code == 400
    assert "Lamb Karahi" in exc_info.value.detail

    # Verify rollback held: prod1 still has its original stock (NOT decremented)
    db.refresh(prod1)
    db.refresh(prod2)
    assert prod1.stock == prod1_stock_before
    assert prod2.stock == 1  # What we set it to


def test_product_on_two_pending_lines_decremented_once_for_summed_quantity(db: Session):
    """Product on two separate PENDING lines is decremented once for the summed quantity."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    prod = db.query(Product).filter(Product.id == db.prod1_id).first()
    stock_before = prod.stock  # 5

    # First send
    add_payload1 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    add_items_to_order(db, order_id, add_payload1)
    send_batch_to_kitchen(db, order_id)

    # Stock now 3
    db.refresh(prod)
    assert prod.stock == stock_before - 2

    # Add the same product again (creates a second PENDING line)
    add_payload2 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    add_items_to_order(db, order_id, add_payload2)

    # Send again
    send_batch_to_kitchen(db, order_id)

    # Stock should be decremented by 2 (the new quantity), not 4
    db.refresh(prod)
    assert prod.stock == stock_before - 4

    # Should have exactly 2 StockMovement rows (one per send)
    movements = db.query(StockMovement).all()
    assert len(movements) == 2
    assert movements[0].quantity_change == -2
    assert movements[1].quantity_change == -2


def test_cannot_send_paid_order(db: Session):
    """Cannot send a PAID order."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),
    ])
    add_items_to_order(db, order_id, add_payload)

    # Mark as PAID
    order.status = "PAID"
    order.payment_method = "CASH"
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        send_batch_to_kitchen(db, order_id)

    assert exc_info.value.status_code == 400
    assert "open order" in exc_info.value.detail


def test_cannot_send_cancelled_order(db: Session):
    """Cannot send a CANCELLED order."""
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

    with pytest.raises(HTTPException) as exc_info:
        send_batch_to_kitchen(db, order_id)

    assert exc_info.value.status_code == 400
    assert "open order" in exc_info.value.detail


def test_send_nonexistent_order_id(db: Session):
    """Cannot send a nonexistent order_id -> 404."""
    with pytest.raises(HTTPException) as exc_info:
        send_batch_to_kitchen(db, 999)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail


def test_order_total_and_subtotal_unchanged_by_sending(db: Session):
    """Order.total and order.subtotal are unchanged by sending."""
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
    order_after_add = add_items_to_order(db, order_id, add_payload)
    subtotal_before_send = order_after_add.subtotal  # 100000
    total_before_send = order_after_add.total  # 100000 + tax

    sent_order = send_batch_to_kitchen(db, order_id)
    assert sent_order.subtotal == subtotal_before_send
    assert sent_order.total == total_before_send


def test_payment_method_still_none_after_sending(db: Session):
    """Order.payment_method is still None after sending."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),
    ])
    add_items_to_order(db, order_id, add_payload)

    sent_order = send_batch_to_kitchen(db, order_id)
    assert sent_order.payment_method is None
