"""Tests for Stage 4, Task B6: update_pending_item() service function."""
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
    create_open_order, add_items_to_order, update_pending_item, send_batch_to_kitchen, pay_order, cancel_order
)
from app.schemas.schemas import OpenOrderCreate, AddItemsIn, OrderItemCreate, UpdatePendingItemIn, PayOrderIn, OrderCancelIn


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

    yield session

    # Cleanup
    session.close()
    engine.raw_connection().close() if hasattr(engine.raw_connection(), 'close') else None
    engine.dispose()
    gc.collect()
    time.sleep(0.1)
    if os.path.exists(db_path):
        for attempt in range(3):
            try:
                os.remove(db_path)
                break
            except OSError:
                if attempt < 2:
                    gc.collect()
                    time.sleep(0.05)


def test_update_pending_item_increase_quantity(db: Session):
    """update_pending_item() increases quantity and recomputes totals."""
    # Create open order and add item
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=2)]))
    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]
    original_subtotal = order.subtotal

    # Update quantity to 3
    updated_order = update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=3))

    assert updated_order.items[0].quantity == 3
    assert updated_order.subtotal == 150000  # 50000 * 3
    assert updated_order.total == 150000
    assert original_subtotal == 100000  # Verify original was 100000


def test_update_pending_item_decrease_quantity(db: Session):
    """update_pending_item() decreases quantity and recomputes totals."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=5)]))
    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Update quantity to 2
    updated_order = update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=2))

    assert updated_order.items[0].quantity == 2
    assert updated_order.subtotal == 100000  # 50000 * 2
    assert updated_order.total == 100000


def test_update_pending_item_quantity_zero_deletes_item(db: Session):
    """update_pending_item() with quantity=0 deletes the item from the order."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=2)]))
    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Update quantity to 0
    updated_order = update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=0))

    assert len(updated_order.items) == 0
    assert updated_order.subtotal == 0
    assert updated_order.total == 0


def test_update_pending_item_zero_quantity_leaves_zero_item_order(db: Session):
    """Removing the last item leaves a 0-item order (not an error)."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=1)]))
    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Delete the only item
    updated_order = update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=0))

    assert len(updated_order.items) == 0
    assert updated_order.subtotal == 0
    assert updated_order.total == 0


def test_update_pending_item_on_disabled_product_when_decreasing(db: Session):
    """Reducing quantity on a DISABLED product still works."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=5)]))
    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Disable the product
    product.available = False
    db.commit()

    # Update quantity downward should still work
    updated_order = update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=2))

    assert updated_order.items[0].quantity == 2
    assert updated_order.subtotal == 100000


def test_update_pending_item_delete_on_disabled_product(db: Session):
    """Deleting an item (quantity=0) on a DISABLED product works."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=3)]))
    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Disable the product
    product.available = False
    db.commit()

    # Delete should still work
    updated_order = update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=0))

    assert len(updated_order.items) == 0
    assert updated_order.subtotal == 0


def test_update_pending_item_price_snapshot(db: Session):
    """item.price is NOT re-read from the product — uses original snapshotted price."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=1)]))
    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Verify original snapshotted price
    assert item.price == 50000

    # Change product price
    product.price = 75000
    db.commit()

    # Update quantity: line_total should use the ORIGINAL snapshotted price
    updated_order = update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=2))
    updated_item = updated_order.items[0]

    assert updated_item.price == 50000  # Original price, not the new one
    assert updated_item.line_total == 100000  # 50000 * 2
    assert updated_order.subtotal == 100000


def test_update_pending_item_preserves_discount_payment_method(db: Session):
    """update_pending_item() preserves discount, payment_method, amount_received, change_amount."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=1)]))
    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Update quantity
    updated_order = update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=2))

    # These fields should remain at defaults
    assert updated_order.discount == 0
    assert updated_order.payment_method is None
    assert updated_order.amount_received == 0
    assert updated_order.change_amount == 0


def test_update_pending_item_increase_on_disabled_product_fails(db: Session):
    """Increasing quantity on a DISABLED product raises 400."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=1)]))
    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Disable the product
    product.available = False
    db.commit()

    # Try to increase quantity
    with pytest.raises(HTTPException) as exc_info:
        update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=2))
    assert exc_info.value.status_code == 400
    assert "disabled" in str(exc_info.value.detail).lower()


def test_update_pending_item_nonexistent_item(db: Session):
    """update_pending_item() with nonexistent item_id raises 404."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))

    with pytest.raises(HTTPException) as exc_info:
        update_pending_item(db, order.id, 999, UpdatePendingItemIn(quantity=1))
    assert exc_info.value.status_code == 404


def test_update_pending_item_item_on_different_order(db: Session):
    """update_pending_item() returns 404 when item belongs to a different order."""
    table_a = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    table_b = db.query(RestaurantTable).filter(RestaurantTable.id == 8).first()

    # Create two orders
    order_a = create_open_order(db, OpenOrderCreate(table_id=table_a.id))
    order_b = create_open_order(db, OpenOrderCreate(table_id=table_b.id))

    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    # Add item to order_a
    add_items_to_order(db, order_a.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=1)]))
    order_a = db.query(Order).filter(Order.id == order_a.id).first()
    item_id = order_a.items[0].id

    # Try to update the item from order_a on order_b
    with pytest.raises(HTTPException) as exc_info:
        update_pending_item(db, order_b.id, item_id, UpdatePendingItemIn(quantity=2))
    assert exc_info.value.status_code == 404  # Not 400


def test_update_pending_item_sent_item_fails(db: Session):
    """update_pending_item() cannot modify an item that has been sent to kitchen."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=2)]))
    send_batch_to_kitchen(db, order.id)

    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Try to update sent item
    with pytest.raises(HTTPException) as exc_info:
        update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=3))
    assert exc_info.value.status_code == 400
    assert "sent to the kitchen" in str(exc_info.value.detail)


def test_update_pending_item_on_paid_order_fails(db: Session):
    """update_pending_item() cannot modify items on a PAID order."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=1)]))
    send_batch_to_kitchen(db, order.id)
    pay_order(db, order.id, PayOrderIn(payment_method="CASH", discount=0, amount_received=50000))

    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    with pytest.raises(HTTPException) as exc_info:
        update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=2))
    assert exc_info.value.status_code == 400


def test_update_pending_item_insufficient_stock(db: Session):
    """update_pending_item() rejects increase when stock is insufficient."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=1)]))
    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Try to increase to quantity 101 (stock is 100)
    with pytest.raises(HTTPException) as exc_info:
        update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=101))
    assert exc_info.value.status_code == 400
    assert "available" in str(exc_info.value.detail).lower()


def test_update_pending_item_stock_check_accounts_for_other_pending(db: Session):
    """Stock check for increase accounts for other PENDING items of the same product."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    # Add one PENDING item via service (quantity 1)
    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=1)]))
    order = db.query(Order).filter(Order.id == order.id).first()
    item_1 = order.items[0]

    # Manually insert a second PENDING item: add_items_to_order aggregates by product_id and merges into existing PENDING lines, so this state is unreachable through the service and represents a defensive check.
    second_item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        product_name=product.name_display,
        quantity=1,
        price=product.price,
        line_total=product.price * 1,
        batch_id=None,
        sent_at=None,
    )
    db.add(second_item)
    db.commit()

    # Now: item_1 (qty 1) + second_item (qty 1) = 2 total pending for this product
    # Stock = 100. Trying to update item_1 to qty 100 should fail because:
    # other_pending = 1, total_needed = 1 + 100 = 101, which exceeds stock of 100
    # Should report "only 99 available" (100 stock - 1 other pending)
    with pytest.raises(HTTPException) as exc_info:
        update_pending_item(db, order.id, item_1.id, UpdatePendingItemIn(quantity=100))
    assert exc_info.value.status_code == 400
    assert "99" in str(exc_info.value.detail)


# --- Stage 4 B8: Remove SENT items ---

def test_remove_sent_item_restores_stock(db: Session):
    """Removing a SENT item restores its stock (B8)."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    # Add item and send to kitchen
    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=2)]))
    send_batch_to_kitchen(db, order.id)

    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]
    stock_after_send = db.query(Product).filter(Product.id == product.id).first().stock

    # Verify stock was decremented
    assert stock_after_send == 98  # 100 - 2

    # Remove the SENT item
    updated_order = update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=0))

    # Verify stock was restored
    product_after = db.query(Product).filter(Product.id == product.id).first()
    assert product_after.stock == 100

    # Verify item is deleted from order
    assert len(updated_order.items) == 0


def test_remove_sent_item_creates_return_movement(db: Session):
    """Removing a SENT item creates a RETURN StockMovement (B8)."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    # Add item and send to kitchen
    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=2)]))
    send_batch_to_kitchen(db, order.id)

    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Count SALE movements
    sale_count = db.query(StockMovement).filter(
        StockMovement.reference == order.order_number,
        StockMovement.movement_type == "SALE",
    ).count()
    assert sale_count == 1

    # Remove the SENT item
    update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=0))

    # Verify one RETURN movement was created
    return_movements = db.query(StockMovement).filter(
        StockMovement.reference == order.order_number,
        StockMovement.movement_type == "RETURN",
    ).all()
    assert len(return_movements) == 1
    assert return_movements[0].item_id == product.id
    assert return_movements[0].quantity_change == 2  # positive, mirrors SALE's -2


def test_remove_sent_item_sale_movement_untouched(db: Session):
    """Original SALE movement remains (append-only ledger, Rule 4)."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    # Add item and send to kitchen
    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=2)]))
    send_batch_to_kitchen(db, order.id)

    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Get the original SALE movement
    sale_movement = db.query(StockMovement).filter(
        StockMovement.reference == order.order_number,
        StockMovement.movement_type == "SALE",
    ).first()
    original_qty_change = sale_movement.quantity_change

    # Remove the SENT item
    update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=0))

    # Verify SALE movement was NOT updated
    sale_after = db.query(StockMovement).filter(StockMovement.id == sale_movement.id).first()
    assert sale_after.quantity_change == original_qty_change  # unchanged (-2)


def test_remove_sent_item_recomputes_totals(db: Session):
    """Removing a SENT item recomputes order totals (B8)."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product1 = db.query(Product).filter(Product.name_key == "chickenbiryani").first()
    product2 = db.query(Product).filter(Product.name_key == "lambkarahi").first()

    # Add two items and send both
    add_items_to_order(db, order.id, AddItemsIn(items=[
        OrderItemCreate(product_id=product1.id, quantity=1),
        OrderItemCreate(product_id=product2.id, quantity=1),
    ]))
    send_batch_to_kitchen(db, order.id)

    order = db.query(Order).filter(Order.id == order.id).first()
    item1 = next(i for i in order.items if i.product_id == product1.id)
    original_total = order.total

    # Remove the first item (Chicken Biryani, 50000)
    updated_order = update_pending_item(db, order.id, item1.id, UpdatePendingItemIn(quantity=0))

    # Subtotal should be reduced by 50000
    assert updated_order.subtotal == 60000  # 110000 - 50000
    assert updated_order.total == 60000  # no tax, no discount


def test_remove_last_sent_item_leaves_zero_item_order(db: Session):
    """Removing the last SENT item leaves order OPEN with 0 items (B8)."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    # Add one item and send it
    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=1)]))
    send_batch_to_kitchen(db, order.id)

    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Remove the only SENT item
    updated_order = update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=0))

    # Order remains OPEN, now empty
    assert updated_order.status == "OPEN"
    assert len(updated_order.items) == 0
    assert updated_order.subtotal == 0
    assert updated_order.total == 0


def test_remove_sent_item_with_custom_reason(db: Session):
    """Removing a SENT item with custom reason stores it in StockMovement.reason (B8)."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    # Add item and send to kitchen
    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=1)]))
    send_batch_to_kitchen(db, order.id)

    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Remove with custom reason
    custom_reason = "Customer changed mind"
    update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=0, reason=custom_reason))

    # Verify RETURN movement has the custom reason
    return_movement = db.query(StockMovement).filter(
        StockMovement.reference == order.order_number,
        StockMovement.movement_type == "RETURN",
    ).first()
    assert return_movement.reason == custom_reason


def test_remove_sent_item_without_reason_uses_default(db: Session):
    """Removing a SENT item without reason uses default 'Item removed' (B8)."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    # Add item and send to kitchen
    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=1)]))
    send_batch_to_kitchen(db, order.id)

    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Remove without reason (reason=None)
    update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=0, reason=None))

    # Verify RETURN movement has default reason
    return_movement = db.query(StockMovement).filter(
        StockMovement.reference == order.order_number,
        StockMovement.movement_type == "RETURN",
    ).first()
    assert return_movement.reason == "Item removed"


def test_cannot_modify_sent_item_with_nonzero_quantity(db: Session):
    """Attempting to change quantity of a SENT item (to non-zero) fails (B8)."""
    table = db.query(RestaurantTable).filter(RestaurantTable.id == 7).first()
    order = create_open_order(db, OpenOrderCreate(table_id=table.id))
    product = db.query(Product).filter(Product.name_key == "chickenbiryani").first()

    # Add item and send to kitchen
    add_items_to_order(db, order.id, AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=2)]))
    send_batch_to_kitchen(db, order.id)

    order = db.query(Order).filter(Order.id == order.id).first()
    item = order.items[0]

    # Try to increase quantity to 3
    with pytest.raises(HTTPException) as exc_info:
        update_pending_item(db, order.id, item.id, UpdatePendingItemIn(quantity=3))
    assert exc_info.value.status_code == 400
    assert "sent to the kitchen" in str(exc_info.value.detail)
