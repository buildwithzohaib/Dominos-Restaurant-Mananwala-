"""Tests for Stage 4, Task B2: add_items_to_order() — add items to running-tab orders."""
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
from app.services.order_service import create_open_order, add_items_to_order
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
    cat_disabled = Category(name_raw="Soups", name_display="Soups", name_key="soups", active=False)
    session.add_all([cat1, cat_disabled])
    session.flush()

    # Seed products with different prices and stock levels
    prod1 = Product(
        category_id=cat1.id,
        name_raw="Chicken Biryani",
        name_display="Chicken Biryani",
        name_key="chickenbiryani",
        price=50000,  # 500 rupees
        stock=10,
        sku="BIRYANI-001",
        min_stock=2,
        unit="Portion",
        available=True,
    )
    prod2 = Product(
        category_id=cat1.id,
        name_raw="Lamb Karahi",
        name_display="Lamb Karahi",
        name_key="lambkarahi",
        price=60000,  # 600 rupees
        stock=15,
        sku="KARAHI-001",
        min_stock=3,
        unit="Portion",
        available=True,
    )
    prod_disabled = Product(
        category_id=cat1.id,
        name_raw="Discontinued Special",
        name_display="Discontinued Special",
        name_key="discontinuedspecial",
        price=40000,
        stock=5,
        sku="DISC-001",
        min_stock=1,
        unit="Portion",
        available=False,
    )
    prod_in_disabled_cat = Product(
        category_id=cat_disabled.id,
        name_raw="Tomato Soup",
        name_display="Tomato Soup",
        name_key="tomatosoup",
        price=20000,
        stock=20,
        sku="SOUP-001",
        min_stock=5,
        unit="Bowl",
        available=True,
    )
    prod_no_stock = Product(
        category_id=cat1.id,
        name_raw="Out of Stock Item",
        name_display="Out of Stock Item",
        name_key="outofstockitem",
        price=35000,
        stock=0,
        sku="OOS-001",
        min_stock=5,
        unit="Portion",
        available=True,
    )
    session.add_all([prod1, prod2, prod_disabled, prod_in_disabled_cat, prod_no_stock])
    session.flush()

    # Seed tables
    table_a = RestaurantTable(id=7, name="Patio A", seats=2, active=True)
    table_b = RestaurantTable(id=8, name="Corner Booth", seats=4, active=True)
    table_closed = RestaurantTable(id=9, name="Garden Side", seats=2, active=False)
    session.add_all([table_a, table_b, table_closed])
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
    session.prod_disabled_id = prod_disabled.id
    session.prod_in_disabled_cat_id = prod_in_disabled_cat.id
    session.prod_no_stock_id = prod_no_stock.id

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


def test_add_items_to_open_order_success(db: Session):
    """Add items to an OPEN order; items appear with batch_id IS None and sent_at IS None."""
    # Create open order
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    # Add items
    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    updated_order = add_items_to_order(db, order_id, add_payload)

    assert len(updated_order.items) == 1
    assert updated_order.items[0].product_id == db.prod1_id
    assert updated_order.items[0].quantity == 2
    assert updated_order.items[0].batch_id is None
    assert updated_order.items[0].sent_at is None


def test_add_items_subtotal_tax_total_correct(db: Session):
    """Subtotal, tax, total are correct for a known tax_rate."""
    # Enable tax
    settings = db.query(Settings).filter(Settings.id == 1).first()
    settings.tax_enabled = True
    settings.tax_rate = 1600  # 16%
    db.commit()

    # Create and add items
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),  # 50000 * 2 = 100000
    ])
    updated_order = add_items_to_order(db, order_id, add_payload)

    # Verify totals
    # subtotal = 100000
    # tax = (100000 * 1600 + 5000) // 10000 = 160005000 // 10000 = 16000
    # total = 100000 + 16000 = 116000
    assert updated_order.subtotal == 100000
    assert updated_order.tax == 16000
    assert updated_order.total == 116000
    assert updated_order.payment_method is None
    assert updated_order.discount == 0


def test_add_items_tax_zero_when_disabled(db: Session):
    """Tax is 0 and total == subtotal when order.tax_rate is 0."""
    settings = db.query(Settings).filter(Settings.id == 1).first()
    settings.tax_enabled = False
    db.commit()

    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=3),  # 50000 * 3 = 150000
    ])
    updated_order = add_items_to_order(db, order_id, add_payload)

    assert updated_order.tax_rate == 0
    assert updated_order.tax == 0
    assert updated_order.total == updated_order.subtotal
    assert updated_order.total == 150000


def test_add_items_second_add_appends_and_recomputes_totals(db: Session):
    """Second add appends more items and recomputes totals over ALL items (running-tab case)."""
    settings = db.query(Settings).filter(Settings.id == 1).first()
    settings.tax_enabled = True
    settings.tax_rate = 1000  # 10%
    db.commit()

    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    # First add
    add_payload1 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),  # 50000
    ])
    order_after_first = add_items_to_order(db, order_id, add_payload1)
    assert len(order_after_first.items) == 1
    assert order_after_first.subtotal == 50000
    # tax = (50000 * 1000 + 5000) // 10000 = 50005000 // 10000 = 5000
    assert order_after_first.tax == 5000
    assert order_after_first.total == 55000

    # Second add
    add_payload2 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod2_id, quantity=1),  # 60000
    ])
    order_after_second = add_items_to_order(db, order_id, add_payload2)
    assert len(order_after_second.items) == 2
    # subtotal = 50000 + 60000 = 110000
    assert order_after_second.subtotal == 110000
    # tax = (110000 * 1000 + 5000) // 10000 = 110005000 // 10000 = 11000
    assert order_after_second.tax == 11000
    assert order_after_second.total == 121000


def test_product_name_and_price_are_snapshots(db: Session):
    """Product name and price are snapshots: changes to Product after adding don't affect OrderItem."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    # Add items
    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    updated_order = add_items_to_order(db, order_id, add_payload)
    item = updated_order.items[0]
    assert item.product_name == "Chicken Biryani"
    assert item.price == 50000

    # Change the product's name and price
    prod = db.query(Product).filter(Product.id == db.prod1_id).first()
    prod.name_display = "Changed Biryani"
    prod.price = 55000
    db.commit()

    # Reload the order and verify the item still has the old values
    order_reloaded = db.query(Order).filter(Order.id == order_id).first()
    item_reloaded = order_reloaded.items[0]
    assert item_reloaded.product_name == "Chicken Biryani"  # unchanged snapshot
    assert item_reloaded.price == 50000  # unchanged snapshot


def test_no_stock_movements_and_stock_unchanged(db: Session):
    """No StockMovement rows exist and Product.stock is unchanged after adding."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    prod = db.query(Product).filter(Product.id == db.prod1_id).first()
    stock_before = prod.stock

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=3),
    ])
    add_items_to_order(db, order_id, add_payload)

    # Verify stock unchanged
    db.refresh(prod)
    assert prod.stock == stock_before

    # Verify no StockMovement rows
    movements = db.query(StockMovement).all()
    assert len(movements) == 0


def test_same_product_twice_in_payload_aggregates(db: Session):
    """Same product listed twice in one payload aggregates into one line with summed quantity."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
        OrderItemCreate(product_id=db.prod1_id, quantity=3),
    ])
    updated_order = add_items_to_order(db, order_id, add_payload)

    # Should create ONE OrderItem with quantity=5, not two separate items
    items_for_prod1 = [item for item in updated_order.items if item.product_id == db.prod1_id]
    assert len(items_for_prod1) == 1
    assert items_for_prod1[0].quantity == 5
    assert items_for_prod1[0].line_total == 50000 * 5


def test_quantity_exceeding_stock_rejected(db: Session):
    """Quantity exceeding available stock -> 400."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    # prod1 has stock=10, try to add 15
    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=15),
    ])

    with pytest.raises(HTTPException) as exc_info:
        add_items_to_order(db, order_id, add_payload)

    assert exc_info.value.status_code == 400
    assert "Chicken Biryani" in exc_info.value.detail
    assert "Only 10" in exc_info.value.detail


def test_cumulative_case_pending_plus_new_exceeds_stock(db: Session):
    """Two adds where RUNNING TOTAL exceeds stock -> 400 on second add."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    # prod1 has stock=10. Add 7 (succeeds)
    add_payload1 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=7),
    ])
    add_items_to_order(db, order_id, add_payload1)

    # Try to add 5 more (7 + 5 = 12 > 10, should fail)
    add_payload2 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=5),
    ])

    with pytest.raises(HTTPException) as exc_info:
        add_items_to_order(db, order_id, add_payload2)

    assert exc_info.value.status_code == 400
    # Available should be 10 - 7 (pending) = 3
    assert "Only 3" in exc_info.value.detail


def test_disabled_product_rejected(db: Session):
    """Disabled product -> 400."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod_disabled_id, quantity=1),
    ])

    with pytest.raises(HTTPException) as exc_info:
        add_items_to_order(db, order_id, add_payload)

    assert exc_info.value.status_code == 400
    assert "Discontinued Special" in exc_info.value.detail
    assert "disabled" in exc_info.value.detail


def test_product_in_disabled_category_rejected(db: Session):
    """Product in a disabled category -> 400."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod_in_disabled_cat_id, quantity=1),
    ])

    with pytest.raises(HTTPException) as exc_info:
        add_items_to_order(db, order_id, add_payload)

    assert exc_info.value.status_code == 400
    assert "Tomato Soup" in exc_info.value.detail
    assert "disabled category" in exc_info.value.detail


def test_out_of_stock_product_rejected(db: Session):
    """Out-of-stock product -> 400."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod_no_stock_id, quantity=1),
    ])

    with pytest.raises(HTTPException) as exc_info:
        add_items_to_order(db, order_id, add_payload)

    assert exc_info.value.status_code == 400
    assert "Out of Stock Item" in exc_info.value.detail
    assert "out of stock" in exc_info.value.detail


def test_nonexistent_product_rejected(db: Session):
    """Nonexistent product -> 400."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=999, quantity=1),
    ])

    with pytest.raises(HTTPException) as exc_info:
        add_items_to_order(db, order_id, add_payload)

    assert exc_info.value.status_code == 400
    assert "not found" in exc_info.value.detail


def test_cannot_add_to_paid_order(db: Session):
    """Cannot add items to a PAID order."""
    # Create an open order first
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    # Set it to PAID
    order.status = "PAID"
    order.payment_method = "CASH"
    db.commit()

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),
    ])

    with pytest.raises(HTTPException) as exc_info:
        add_items_to_order(db, order_id, add_payload)

    assert exc_info.value.status_code == 400
    assert "open order" in exc_info.value.detail


def test_cannot_add_to_cancelled_order(db: Session):
    """Cannot add items to a CANCELLED order."""
    # Create an open order first
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    # Set it to CANCELLED
    order.status = "CANCELLED"
    db.commit()

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),
    ])

    with pytest.raises(HTTPException) as exc_info:
        add_items_to_order(db, order_id, add_payload)

    assert exc_info.value.status_code == 400
    assert "open order" in exc_info.value.detail


def test_adding_to_nonexistent_order_id(db: Session):
    """Cannot add to a nonexistent order_id -> 404."""
    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),
    ])

    with pytest.raises(HTTPException) as exc_info:
        add_items_to_order(db, 999, add_payload)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail


def test_payment_method_stays_none(db: Session):
    """payment_method is still None after adding items."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),
    ])
    updated_order = add_items_to_order(db, order_id, add_payload)

    assert updated_order.payment_method is None


def test_discount_stays_zero(db: Session):
    """discount is still 0 after adding items."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=1),
    ])
    updated_order = add_items_to_order(db, order_id, add_payload)

    assert updated_order.discount == 0


def test_add_multiple_different_products(db: Session):
    """Add multiple different products in one call."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    add_payload = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),  # 50000 * 2 = 100000
        OrderItemCreate(product_id=db.prod2_id, quantity=1),  # 60000 * 1 = 60000
    ])
    updated_order = add_items_to_order(db, order_id, add_payload)

    assert len(updated_order.items) == 2
    assert updated_order.subtotal == 160000
    # No tax (tax_rate=0 by default), so total = subtotal
    assert updated_order.total == 160000


def test_pending_lines_merge_on_second_add(db: Session):
    """Add 2 of a product, then add 3 more -> exactly ONE OrderItem, quantity 5, line_total = price * 5."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    # First add: 2 of prod1
    add_payload1 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),  # 50000 * 2 = 100000
    ])
    order_after_first = add_items_to_order(db, order_id, add_payload1)
    assert len(order_after_first.items) == 1
    assert order_after_first.items[0].quantity == 2
    assert order_after_first.items[0].line_total == 100000

    # Second add: 3 more of prod1
    add_payload2 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=3),
    ])
    order_after_second = add_items_to_order(db, order_id, add_payload2)

    # Should still be exactly ONE item, with quantity 5
    assert len(order_after_second.items) == 1
    assert order_after_second.items[0].product_id == db.prod1_id
    assert order_after_second.items[0].quantity == 5
    assert order_after_second.items[0].line_total == 50000 * 5


def test_merged_line_keeps_original_snapshot_price(db: Session):
    """A merged line keeps its ORIGINAL snapshotted price."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    # First add: 2 of prod1 at 50000
    add_payload1 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    order_after_first = add_items_to_order(db, order_id, add_payload1)
    assert order_after_first.items[0].price == 50000
    assert order_after_first.items[0].line_total == 100000

    # Change the product's price
    prod = db.query(Product).filter(Product.id == db.prod1_id).first()
    prod.price = 60000
    db.commit()

    # Second add: 3 more of prod1
    add_payload2 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=3),
    ])
    order_after_second = add_items_to_order(db, order_id, add_payload2)

    # The line should keep its original price (50000) and compute line_total with it
    assert order_after_second.items[0].price == 50000  # unchanged snapshot
    assert order_after_second.items[0].quantity == 5
    assert order_after_second.items[0].line_total == 50000 * 5  # NOT 60000 * 5


def test_sent_lines_not_merged_separate_pending_created(db: Session):
    """If a line is already sent (batch_id NOT NULL), adding that product again creates a separate PENDING line."""
    create_payload = OpenOrderCreate(table_id=db.table_a_id)
    order = create_open_order(db, create_payload)
    order_id = order.id

    # First add: 2 of prod1
    add_payload1 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=2),
    ])
    order_after_first = add_items_to_order(db, order_id, add_payload1)
    assert len(order_after_first.items) == 1
    sent_item_id = order_after_first.items[0].id

    # Mark the line as sent (batch_id = 1)
    item_row = db.query(OrderItem).filter(OrderItem.id == sent_item_id).first()
    item_row.batch_id = 1
    db.commit()

    # Second add: 3 more of prod1
    add_payload2 = AddItemsIn(items=[
        OrderItemCreate(product_id=db.prod1_id, quantity=3),
    ])
    order_after_second = add_items_to_order(db, order_id, add_payload2)

    # Should now have TWO items for prod1: one sent, one pending
    assert len(order_after_second.items) == 2
    items_prod1 = [item for item in order_after_second.items if item.product_id == db.prod1_id]
    assert len(items_prod1) == 2

    # First should be the sent one (batch_id=1, quantity=2)
    sent = next(item for item in items_prod1 if item.batch_id == 1)
    assert sent.quantity == 2

    # Second should be the new pending one (batch_id=None, quantity=3)
    pending = next(item for item in items_prod1 if item.batch_id is None)
    assert pending.quantity == 3
