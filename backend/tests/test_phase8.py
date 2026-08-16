"""
PHASE 8 Testing Suite - Cancellation + Inventory Restoration
Tests all requirements and edge cases for Phase 8 implementation.
"""

import sys
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.database import Base
from app.models.models import Product, Category, Order, OrderItem, StockMovement
from app.services.order_service import create_order, cancel_order
from app.schemas.schemas import OrderCreate, OrderItemCreate, OrderCancelIn
from app.utils.normalization import normalize_display, derive_key

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory SQLite database for each test"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    yield db
    db.close()

def setup_test_data(db, category_name="Beverages"):
    """Create test products and categories in the provided session"""
    # Create category with unique name to avoid conflicts between tests
    category = Category(
        name_raw=category_name,
        name_display=normalize_display(category_name),
        name_key=derive_key(category_name),
        active=True
    )
    db.add(category)
    try:
        db.flush()
    except Exception:
        # Category might already exist from previous test, try to fetch it
        db.rollback()
        category = db.query(Category).filter(Category.name_key == derive_key(category_name)).first()
        if not category:
            raise

    # Create test products
    products = [
        Product(
            category_id=category.id,
            name_raw="Pepsi",
            name_display=normalize_display("Pepsi"),
            name_key=derive_key("Pepsi"),
            price=8000,
            stock=20,
            sku="PEPSI-001",
            min_stock=5,
            unit="Bottle",
            purchase_price=4000,
            available=True
        ),
        Product(
            category_id=category.id,
            name_raw="Fries",
            name_display=normalize_display("Fries"),
            name_key=derive_key("Fries"),
            price=15000,
            stock=30,
            sku="FRIES-001",
            min_stock=10,
            unit="Portion",
            purchase_price=7500,
            available=True
        ),
        Product(
            category_id=category.id,
            name_raw="Chicken Nuggets",
            name_display=normalize_display("Chicken Nuggets"),
            name_key=derive_key("Chicken Nuggets"),
            price=25000,
            stock=15,
            sku="NUGGETS-001",
            min_stock=5,
            unit="Piece",
            purchase_price=12500,
            available=True
        ),
    ]

    for product in products:
        db.add(product)

    db.commit()
    db.refresh(category)
    for product in products:
        db.refresh(product)

    result = {"category": category, "products": {p.name_display: p for p in products}}
    return result

def test_single_item_cancellation(db_session):
    """Test 1: Single item cancellation and inventory restoration"""
    print("\n" + "="*60)
    print("TEST 1: Single Item Cancellation")
    print("="*60)

    db = db_session
    setup = setup_test_data(db)
    pepsi = setup["products"]["Pepsi"]

    initial_stock = pepsi.stock
    print(f"Initial stock: {initial_stock}")

    # Create order
    payload = OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[OrderItemCreate(product_id=pepsi.id, quantity=2)],
        discount=0,
        tax_rate=0,
        payment_method="CASH",
        amount_received=20000
    )

    order = create_order(db, payload)
    print(f"Order created: {order.order_number}")

    # Verify stock decreased
    db.refresh(pepsi)
    stock_after_sale = pepsi.stock
    print(f"Stock after sale: {stock_after_sale} (should be {initial_stock - 2})")
    assert stock_after_sale == initial_stock - 2, "Stock not decreased after sale"

    # Verify SALE movement exists
    sale_movements = db.query(StockMovement).filter(
        StockMovement.reference == order.order_number,
        StockMovement.movement_type == "SALE"
    ).all()
    print(f"SALE movements: {len(sale_movements)}")
    assert len(sale_movements) == 1, "SALE movement not created"

    # Cancel order
    cancel_payload = OrderCancelIn(
        reason="CUSTOMER_CHANGED_ORDER",
        note=None
    )

    cancelled_order = cancel_order(db, order.id, cancel_payload)
    print(f"Order cancelled: {cancelled_order.status}")
    assert cancelled_order.status == "CANCELLED", "Order not marked as CANCELLED"

    # Verify stock restored
    db.refresh(pepsi)
    stock_after_cancel = pepsi.stock
    print(f"Stock after cancel: {stock_after_cancel} (should be {initial_stock})")
    assert stock_after_cancel == initial_stock, "Stock not restored correctly"

    # Verify CANCELLATION movement exists
    cancel_movements = db.query(StockMovement).filter(
        StockMovement.reference == order.order_number,
        StockMovement.movement_type == "CANCELLATION"
    ).all()
    print(f"CANCELLATION movements: {len(cancel_movements)}")
    assert len(cancel_movements) == 1, "CANCELLATION movement not created"

    # Verify SALE movement still exists and unchanged
    sale_movements = db.query(StockMovement).filter(
        StockMovement.reference == order.order_number,
        StockMovement.movement_type == "SALE"
    ).all()
    print(f"SALE movements still exist: {len(sale_movements)}")
    assert len(sale_movements) == 1, "SALE movement was deleted"
    assert sale_movements[0].quantity_change == -2, "SALE movement was modified"

    print("[PASS] TEST 1 PASSED")

def test_multi_item_cancellation(db_session):
    """Test 2: Multi-item cancellation"""
    print("\n" + "="*60)
    print("TEST 2: Multi-Item Cancellation")
    print("="*60)

    db = db_session
    setup = setup_test_data(db)
    pepsi = setup["products"]["Pepsi"]
    fries = setup["products"]["Fries"]
    nuggets = setup["products"]["Chicken Nuggets"]

    initial_stocks = {
        "Pepsi": pepsi.stock,
        "Fries": fries.stock,
        "Nuggets": nuggets.stock
    }
    print(f"Initial stocks: {initial_stocks}")

    # Create order with multiple items
    payload = OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[
            OrderItemCreate(product_id=pepsi.id, quantity=2),
            OrderItemCreate(product_id=fries.id, quantity=3),
            OrderItemCreate(product_id=nuggets.id, quantity=1),
        ],
        discount=0,
        tax_rate=0,
        payment_method="CASH",
        amount_received=100000
    )

    order = create_order(db, payload)
    print(f"Order created: {order.order_number}")

    # Verify all stocks decreased
    db.refresh(pepsi)
    db.refresh(fries)
    db.refresh(nuggets)

    stocks_after_sale = {
        "Pepsi": pepsi.stock,
        "Fries": fries.stock,
        "Nuggets": nuggets.stock
    }
    print(f"Stocks after sale: {stocks_after_sale}")

    assert pepsi.stock == initial_stocks["Pepsi"] - 2, "Pepsi stock incorrect"
    assert fries.stock == initial_stocks["Fries"] - 3, "Fries stock incorrect"
    assert nuggets.stock == initial_stocks["Nuggets"] - 1, "Nuggets stock incorrect"

    # Cancel order
    cancel_payload = OrderCancelIn(
        reason="WRONG_ORDER",
        note=None
    )

    cancelled_order = cancel_order(db, order.id, cancel_payload)
    print(f"Order cancelled: {cancelled_order.status}")

    # Verify all stocks restored
    db.refresh(pepsi)
    db.refresh(fries)
    db.refresh(nuggets)

    stocks_after_cancel = {
        "Pepsi": pepsi.stock,
        "Fries": fries.stock,
        "Nuggets": nuggets.stock
    }
    print(f"Stocks after cancel: {stocks_after_cancel}")

    assert pepsi.stock == initial_stocks["Pepsi"], "Pepsi stock not restored"
    assert fries.stock == initial_stocks["Fries"], "Fries stock not restored"
    assert nuggets.stock == initial_stocks["Nuggets"], "Nuggets stock not restored"

    # Verify all CANCELLATION movements exist
    cancel_movements = db.query(StockMovement).filter(
        StockMovement.reference == order.order_number,
        StockMovement.movement_type == "CANCELLATION"
    ).all()
    print(f"CANCELLATION movements: {len(cancel_movements)}")
    assert len(cancel_movements) == 3, "Not all CANCELLATION movements created"

    print("✅ TEST 2 PASSED")

def test_current_stock_incremented(db_session):
    """Test 3: Current stock is incremented, not historical stock restored"""
    print("\n" + "="*60)
    print("TEST 3: Current Stock Incremented (Not Historical)")
    print("="*60)

    db = db_session
    setup = setup_test_data(db)
    pepsi = setup["products"]["Pepsi"]

    initial_stock = pepsi.stock
    print(f"Initial stock: {initial_stock}")

    # Create and complete order
    payload = OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[OrderItemCreate(product_id=pepsi.id, quantity=2)],
        discount=0,
        tax_rate=0,
        payment_method="CASH",
        amount_received=20000
    )

    order = create_order(db, payload)
    db.refresh(pepsi)
    stock_after_sale = pepsi.stock
    print(f"After sale: {stock_after_sale}")

    # Add more stock (simulating a purchase)
    pepsi.stock += 10
    db.commit()
    db.refresh(pepsi)
    print(f"After purchase (+10): {pepsi.stock}")

    # Cancel the original order
    cancel_payload = OrderCancelIn(
        reason="CUSTOMER_CHANGED_ORDER",
        note=None
    )

    cancelled_order = cancel_order(db, order.id, cancel_payload)
    db.refresh(pepsi)
    stock_after_cancel = pepsi.stock
    print(f"After cancel: {stock_after_cancel}")

    # Should be: 18 - 2 = 16, + 10 = 26, + 2 = 28 (not 20)
    expected = initial_stock - 2 + 10 + 2  # = 30
    print(f"Expected: {expected}, Actual: {stock_after_cancel}")
    assert stock_after_cancel == expected, f"Stock should be {expected}, got {stock_after_cancel}"

    print("✅ TEST 3 PASSED")

def test_double_cancellation_protection(db_session):
    """Test 4: Double cancellation protection"""
    print("\n" + "="*60)
    print("TEST 4: Double Cancellation Protection")
    print("="*60)

    db = db_session
    setup = setup_test_data(db)
    pepsi = setup["products"]["Pepsi"]

    initial_stock = pepsi.stock

    # Create order
    payload = OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[OrderItemCreate(product_id=pepsi.id, quantity=2)],
        discount=0,
        tax_rate=0,
        payment_method="CASH",
        amount_received=20000
    )

    order = create_order(db, payload)
    print(f"Order created: {order.order_number}")

    # First cancellation should succeed
    cancel_payload = OrderCancelIn(
        reason="CUSTOMER_CHANGED_ORDER",
        note=None
    )

    try:
        cancelled_order = cancel_order(db, order.id, cancel_payload)
        print(f"First cancellation: SUCCESS - Status: {cancelled_order.status}")
    except Exception as e:
        print(f"First cancellation FAILED: {e}")
        raise

    # Second cancellation should fail
    db.refresh(pepsi)
    stock_after_first_cancel = pepsi.stock
    print(f"Stock after first cancel: {stock_after_first_cancel}")

    try:
        cancelled_order = cancel_order(db, order.id, cancel_payload)
        print(f"Second cancellation: UNEXPECTED SUCCESS - Status: {cancelled_order.status}")
        raise AssertionError("Second cancellation should have failed")
    except Exception as e:
        if "already been cancelled" in str(e):
            print(f"Second cancellation: CORRECTLY REJECTED - {e}")
        else:
            raise

    # Verify stock was only restored once
    db.refresh(pepsi)
    stock_after_second_attempt = pepsi.stock
    print(f"Stock after second attempt: {stock_after_second_attempt}")
    assert stock_after_second_attempt == initial_stock, "Stock was restored twice"
    assert stock_after_second_attempt == stock_after_first_cancel, "Stock changed between attempts"

    print("✅ TEST 4 PASSED")

def test_stock_movement_audit_trail(db_session):
    """Test 6: Verify stock movement audit trail"""
    print("\n" + "="*60)
    print("TEST 6: Stock Movement Audit Trail")
    print("="*60)

    db = db_session
    setup = setup_test_data(db)
    pepsi = setup["products"]["Pepsi"]

    # Create order
    payload = OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[OrderItemCreate(product_id=pepsi.id, quantity=2)],
        discount=0,
        tax_rate=0,
        payment_method="CASH",
        amount_received=20000
    )

    order = create_order(db, payload)
    print(f"Order created: {order.order_number}")

    # Get SALE movement
    sale_movement = db.query(StockMovement).filter(
        StockMovement.reference == order.order_number,
        StockMovement.movement_type == "SALE"
    ).first()

    print(f"SALE movement: {sale_movement.movement_type}, change={sale_movement.quantity_change}")
    assert sale_movement.quantity_change == -2, "SALE quantity incorrect"

    # Cancel order
    cancel_payload = OrderCancelIn(
        reason="CUSTOMER_CHANGED_ORDER",
        note=None
    )

    cancel_order(db, order.id, cancel_payload)

    # Get CANCELLATION movement
    cancel_movement = db.query(StockMovement).filter(
        StockMovement.reference == order.order_number,
        StockMovement.movement_type == "CANCELLATION"
    ).first()

    print(f"CANCELLATION movement: {cancel_movement.movement_type}, change={cancel_movement.quantity_change}")
    assert cancel_movement.quantity_change == 2, "CANCELLATION quantity incorrect"

    # Verify both reference the same order
    print(f"SALE references: {sale_movement.reference}")
    print(f"CANCELLATION references: {cancel_movement.reference}")
    assert sale_movement.reference == cancel_movement.reference, "References don't match"

    # Verify SALE was not modified
    db.refresh(sale_movement)
    print(f"SALE unchanged: {sale_movement.quantity_change == -2}")
    assert sale_movement.quantity_change == -2, "SALE movement was modified"

    print("✅ TEST 6 PASSED")

def run_all_tests():
    """Run all Phase 8 tests"""
    print("\n" + "="*60)
    print("PHASE 8 TEST SUITE")
    print("="*60)

    tests = [
        test_single_item_cancellation,
        test_multi_item_cancellation,
        test_current_stock_incremented,
        test_double_cancellation_protection,
        test_stock_movement_audit_trail,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAIL] TEST FAILED: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)

    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
