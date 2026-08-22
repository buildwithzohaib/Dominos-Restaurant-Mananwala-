"""
Cost Snapshot Testing Suite (Stage 8 Step 1)

Tests that verify cost is captured on order items at the moment items are added,
and that changing the product's purchase_price afterward does not affect already-
recorded order items. Uses fresh temporary database per test.
"""

import pytest
import tempfile
import os
import gc
import time
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.database import Base
from app.models.models import Product, Category, Order, OrderItem, RestaurantTable, Settings
from app.schemas.schemas import OrderCreate, OrderItemCreate, OpenOrderCreate, AddItemsIn
from app.services.order_service import create_order, create_open_order, add_items_to_order


@pytest.fixture(scope="function")
def engine():
    """Create a fresh temporary SQLite engine for each test."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        test_engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(bind=test_engine)
        yield test_engine
    finally:
        test_engine.dispose()
        gc.collect()
        time.sleep(0.1)
        if os.path.exists(db_path):
            for attempt in range(5):
                try:
                    os.remove(db_path)
                    break
                except OSError:
                    if attempt < 4:
                        time.sleep(0.1)


@pytest.fixture(scope="function")
def db(engine):
    """Create a database session for each test with seeded data."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    # Seed Settings
    settings = Settings(id=1, restaurant_name="Test Restaurant")
    session.add(settings)
    session.flush()

    # Seed Category (name_raw, name_display, name_key required per models.py)
    category = Category(name_raw="Drinks", name_display="Drinks", name_key="drinks", active=True)
    session.add(category)
    session.flush()
    category_id = category.id

    # Seed Table (name, seats, active)
    table = RestaurantTable(name="T1", seats=4, active=True)
    session.add(table)
    session.flush()
    table_id = table.id

    # Seed Product with purchase_price = 5000 (Rs. 50)
    # All fields match models.py exactly
    product = Product(
        category_id=category_id,
        name_raw="Coffee",
        name_display="Coffee",
        name_key="coffee",
        price=10000,  # Rs. 100 selling price (paisa)
        stock=100,
        image=None,
        image_hash=None,
        available=True,
        sku="COFFEE-001",
        min_stock=5,
        unit="Cup",
        purchase_price=5000,  # Rs. 50 cost (paisa)
    )
    session.add(product)
    session.flush()
    product_id = product.id

    session.commit()

    # Expose seeded IDs to tests
    session.category_id = category_id
    session.table_id = table_id
    session.product_id = product_id

    yield session
    session.close()


# ============================================================================
# COST SNAPSHOT TESTS
# ============================================================================

class TestCostSnapshotSingleShot:
    """Cost snapshot in single-shot order creation."""

    def test_item_stores_cost_equal_to_product_purchase_price(self, db):
        """Item created in create_order() stores cost from product.purchase_price"""
        payload = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_id, quantity=2)],
            discount=0,
            amount_received=20000,
            payment_method="CASH",
        )
        order = create_order(db, payload)

        assert len(order.items) == 1
        item = order.items[0]
        assert item.cost == 5000  # product.purchase_price
        assert item.price == 10000  # product.price
        assert item.product_id == db.product_id

    def test_cost_none_when_purchase_price_is_zero(self, db):
        """Product with purchase_price=0 still stores it (not substituted to non-zero)"""
        # Update product's purchase_price to 0
        product = db.query(Product).filter(Product.id == db.product_id).first()
        product.purchase_price = 0
        db.commit()

        payload = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_id, quantity=1)],
            discount=0,
            amount_received=10000,
            payment_method="CASH",
        )
        order = create_order(db, payload)

        item = order.items[0]
        assert item.cost == 0  # zero is valid, not None

    def test_changing_purchase_price_after_order_does_not_affect_item_cost(self, db):
        """Historical order item's cost remains unchanged when product price changes"""
        # Create order with product.purchase_price = 5000
        payload = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_id, quantity=1)],
            discount=0,
            amount_received=10000,
            payment_method="CASH",
        )
        order = create_order(db, payload)
        original_cost = order.items[0].cost
        assert original_cost == 5000

        # Change product's purchase_price to 8000
        product = db.query(Product).filter(Product.id == db.product_id).first()
        product.purchase_price = 8000
        db.commit()

        # Query the order item again: cost should be unchanged
        item = db.query(OrderItem).filter(OrderItem.order_id == order.id).first()
        assert item.cost == original_cost  # Still 5000, not 8000
        assert product.purchase_price == 8000  # Product did change


class TestCostSnapshotDineIn:
    """Cost snapshot in DINE_IN running tab orders."""

    def test_item_added_to_open_order_stores_cost(self, db):
        """Item added to DINE_IN tab via add_items_to_order() stores cost"""
        # Create open order
        open_payload = OpenOrderCreate(table_id=db.table_id)
        order = create_open_order(db, open_payload)

        # Add items
        add_payload = AddItemsIn(items=[OrderItemCreate(product_id=db.product_id, quantity=3)])
        order = add_items_to_order(db, order.id, add_payload)

        assert len(order.items) == 1
        item = order.items[0]
        assert item.cost == 5000  # product.purchase_price at add time
        assert item.price == 10000  # product.price
        assert item.batch_id is None  # PENDING

    def test_dine_in_item_cost_snapshot_independent_of_later_change(self, db):
        """DINE_IN item's cost snapshot is independent of later purchase_price changes"""
        # Create and add item
        open_payload = OpenOrderCreate(table_id=db.table_id)
        order = create_open_order(db, open_payload)

        add_payload = AddItemsIn(items=[OrderItemCreate(product_id=db.product_id, quantity=1)])
        order = add_items_to_order(db, order.id, add_payload)
        item_id = order.items[0].id
        original_cost = order.items[0].cost
        assert original_cost == 5000

        # Change purchase_price
        product = db.query(Product).filter(Product.id == db.product_id).first()
        product.purchase_price = 7500
        db.commit()

        # Item's cost unchanged
        item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
        assert item.cost == original_cost
        assert product.purchase_price == 7500

    def test_multiple_items_each_store_own_cost_snapshot(self, db):
        """Multiple items on same order each capture their own cost at add time"""
        # Create product 2 (all fields match models.py)
        product2 = Product(
            category_id=1,
            name_raw="Tea",
            name_display="Tea",
            name_key="tea",
            price=8000,
            stock=100,
            image=None,
            image_hash=None,
            available=True,
            sku="TEA-001",
            min_stock=5,
            unit="Cup",
            purchase_price=3000,  # Different cost
        )
        db.add(product2)
        db.flush()
        product2_id = product2.id

        # Create order with both products
        payload = OrderCreate(
            order_type="TAKEAWAY",
            items=[
                OrderItemCreate(product_id=db.product_id, quantity=1),  # cost 5000
                OrderItemCreate(product_id=product2_id, quantity=1),     # cost 3000
            ],
            discount=0,
            amount_received=20000,
            payment_method="CASH",
        )
        order = create_order(db, payload)

        assert len(order.items) == 2
        # First item should have first product's cost
        item1 = next(i for i in order.items if i.product_id == db.product_id)
        assert item1.cost == 5000

        # Second item should have second product's cost
        item2 = next(i for i in order.items if i.product_id == product2_id)
        assert item2.cost == 3000

    def test_cost_captured_at_item_add_time_not_order_pay_time(self, db):
        """Cost is captured when item is added, not when order is paid later"""
        # Create open order
        open_payload = OpenOrderCreate(table_id=db.table_id)
        order = create_open_order(db, open_payload)

        # Add item (cost = 5000 at this moment)
        add_payload = AddItemsIn(items=[OrderItemCreate(product_id=db.product_id, quantity=1)])
        order = add_items_to_order(db, order.id, add_payload)
        cost_at_add = order.items[0].cost
        assert cost_at_add == 5000

        # Change purchase_price before payment
        product = db.query(Product).filter(Product.id == db.product_id).first()
        product.purchase_price = 12000
        db.commit()

        # Item's cost is still 5000 (was captured at add time)
        item = db.query(OrderItem).filter(OrderItem.order_id == order.id).first()
        assert item.cost == 5000
        assert product.purchase_price == 12000


class TestCostNullHandling:
    """Tests for cost NULL scenarios.

    purchase_price is NOT nullable (default 0 in models.py), so NULL cost only
    appears in pre-Stage 8 order items created before this migration.
    """

    def test_product_without_purchase_price_snapshots_zero(self, db):
        """Product without explicit purchase_price defaults to 0, item's cost is 0"""
        # Create product without passing purchase_price — it defaults to 0 per models.py
        product = Product(
            category_id=1,
            name_raw="Unnamed Cost Item",
            name_display="Unnamed Cost Item",
            name_key="unnamedcostitem",
            price=5000,
            stock=50,
            image=None,
            image_hash=None,
            available=True,
            sku="UNNAMED-001",
            min_stock=5,
            unit="Piece",
            # purchase_price NOT passed — defaults to 0
        )
        db.add(product)
        db.flush()
        product_id = product.id
        db.commit()

        # Create order with this product
        payload = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=product_id, quantity=1)],
            discount=0,
            amount_received=5000,
            payment_method="CASH",
        )
        order = create_order(db, payload)

        # Item's cost should be 0 (the default)
        item = order.items[0]
        assert item.cost == 0  # Not None, but 0
        assert item.price == 5000
        assert order.status == "PAID"

        # Important: cost=0 means "cost was never entered", NOT "item is free".
        # Profit reports must exclude these lines rather than counting them as pure margin.

    def test_pre_stage8_order_item_can_have_null_cost(self, db):
        """Pre-Stage 8 order items have NULL cost; the column accepts it for historical rows"""
        # Create an order first
        payload = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_id, quantity=1)],
            discount=0,
            amount_received=10000,
            payment_method="CASH",
        )
        order = create_order(db, payload)

        # Manually insert an OrderItem with cost=NULL, simulating a pre-Stage 8 item
        # (This would come from a row created before the cost column existed)
        from sqlalchemy import insert
        stmt = insert(OrderItem).values(
            order_id=order.id,
            product_id=db.product_id,
            product_name="Historical Item",
            quantity=2,
            price=3000,
            line_total=6000,
            cost=None,  # NULL cost, as pre-Stage 8 items have
            batch_id=None,
            sent_at=None,
        )
        db.execute(stmt)
        db.commit()

        # Read it back: cost should be None
        historical_item = db.query(OrderItem).filter(
            OrderItem.product_name == "Historical Item"
        ).first()
        assert historical_item.cost is None
        assert historical_item.price == 3000
        assert historical_item.quantity == 2
