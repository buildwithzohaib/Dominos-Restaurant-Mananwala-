"""
PHASE 8 Testing Suite - Cancellation + Inventory Restoration
Simplified version focusing on core functionality
"""

import sys
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.database import Base
from app.models.models import Product, Category
from app.services.order_service import create_order, cancel_order
from app.schemas.schemas import OrderCreate, OrderItemCreate, OrderCancelIn

# Create a persistent database for testing
engine = create_engine("sqlite:///test_phase8.db", echo=False)
Base.metadata.drop_all(bind=engine)  # Clean start
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

test_counter = 0

def setup_test_data(db):
    """Create test products and categories once"""
    global test_counter
    test_counter += 1

    # Create category (only first time)
    category = db.query(Category).filter(Category.name == "Beverages").first()
    if not category:
        category = Category(name="Beverages", active=True)
        db.add(category)
        db.commit()

    # Create unique products for this test run
    products = []
    for i, (name, sku) in enumerate([
        ("Pepsi", f"PEPSI-{test_counter}"),
        ("Fries", f"FRIES-{test_counter}"),
        ("Nuggets", f"NUGGETS-{test_counter}")
    ]):
        product = Product(
            category_id=category.id,
            name=name,
            price=Decimal("80" if i == 0 else "150" if i == 1 else "250"),
            stock=20 if i == 0 else 30 if i == 1 else 15,
            sku=sku,
            min_stock=5 if i != 1 else 10,
            unit="Bottle" if i == 0 else "Portion" if i == 1 else "Piece",
            purchase_price=Decimal("40" if i == 0 else "75" if i == 1 else "125"),
            available=True
        )
        db.add(product)
        products.append(product)

    db.commit()
    for product in products:
        db.refresh(product)

    return {p.name: p for p in products}

def test_1_single_item_cancellation():
    """Test 1: Single item cancellation and inventory restoration"""
    print("\nTEST 1: Single Item Cancellation")
    print("-" * 40)

    db = SessionLocal()
    products = setup_test_data(db)
    pepsi = products["Pepsi"]

    initial_stock = pepsi.stock
    print(f"Initial stock: {initial_stock}")

    # Create order
    order = create_order(db, OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[OrderItemCreate(product_id=pepsi.id, quantity=2)],
        discount=Decimal("0"),
        tax_rate=Decimal("0"),
        payment_method="CASH",
        amount_received=Decimal("200")
    ))

    print(f"Order created: {order.order_number}")

    # Verify stock decreased
    db.refresh(pepsi)
    assert pepsi.stock == initial_stock - 2
    print(f"Stock after sale: {pepsi.stock} [PASS]")

    # Cancel order
    cancelled = cancel_order(db, order.id, OrderCancelIn(reason="CUSTOMER_CHANGED_ORDER"))
    assert cancelled.status == "CANCELLED"
    print(f"Order cancelled: {cancelled.status} [PASS]")

    # Verify stock restored
    db.refresh(pepsi)
    assert pepsi.stock == initial_stock
    print(f"Stock after cancel: {pepsi.stock} [PASS]")

    db.close()
    return True

def test_2_multi_item_cancellation():
    """Test 2: Multi-item cancellation"""
    print("\nTEST 2: Multi-Item Cancellation")
    print("-" * 40)

    db = SessionLocal()
    products = setup_test_data(db)
    pepsi = products["Pepsi"]
    fries = products["Fries"]
    nuggets = products["Nuggets"]

    initial_stocks = {
        "Pepsi": pepsi.stock,
        "Fries": fries.stock,
        "Nuggets": nuggets.stock
    }

    # Create order
    order = create_order(db, OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[
            OrderItemCreate(product_id=pepsi.id, quantity=2),
            OrderItemCreate(product_id=fries.id, quantity=3),
            OrderItemCreate(product_id=nuggets.id, quantity=1),
        ],
        discount=Decimal("0"),
        tax_rate=Decimal("0"),
        payment_method="CASH",
        amount_received=Decimal("1000")
    ))

    print(f"Order created: {order.order_number}")

    # Verify stocks decreased
    db.refresh(pepsi)
    db.refresh(fries)
    db.refresh(nuggets)

    assert pepsi.stock == initial_stocks["Pepsi"] - 2
    assert fries.stock == initial_stocks["Fries"] - 3
    assert nuggets.stock == initial_stocks["Nuggets"] - 1
    print("Stocks decreased correctly [PASS]")

    # Cancel order
    cancel_order(db, order.id, OrderCancelIn(reason="WRONG_ORDER"))

    # Verify all stocks restored
    db.refresh(pepsi)
    db.refresh(fries)
    db.refresh(nuggets)

    assert pepsi.stock == initial_stocks["Pepsi"]
    assert fries.stock == initial_stocks["Fries"]
    assert nuggets.stock == initial_stocks["Nuggets"]
    print("All stocks restored correctly [PASS]")

    db.close()
    return True

def test_3_current_stock_incremented():
    """Test 3: Current stock is incremented, not historical stock restored"""
    print("\nTEST 3: Current Stock Incremented (Not Historical)")
    print("-" * 40)

    db = SessionLocal()
    products = setup_test_data(db)
    pepsi = products["Pepsi"]

    initial_stock = pepsi.stock

    # Create and complete order
    order = create_order(db, OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[OrderItemCreate(product_id=pepsi.id, quantity=2)],
        discount=Decimal("0"),
        tax_rate=Decimal("0"),
        payment_method="CASH",
        amount_received=Decimal("200")
    ))

    db.refresh(pepsi)
    stock_after_sale = pepsi.stock
    print(f"After sale: {stock_after_sale}")

    # Add more stock (simulating a purchase)
    pepsi.stock += 10
    db.commit()
    db.refresh(pepsi)
    print(f"After purchase (+10): {pepsi.stock}")

    # Cancel the original order
    cancel_order(db, order.id, OrderCancelIn(reason="CUSTOMER_CHANGED_ORDER"))

    db.refresh(pepsi)
    stock_after_cancel = pepsi.stock
    print(f"After cancel: {stock_after_cancel}")

    # Should be: 20 - 2 = 18, + 10 = 28, + 2 = 30 (not 20)
    expected = initial_stock - 2 + 10 + 2
    assert stock_after_cancel == expected, f"Expected {expected}, got {stock_after_cancel}"
    print(f"Expected {expected}: {stock_after_cancel} [PASS]")

    db.close()
    return True

def test_4_double_cancellation_protection():
    """Test 4: Double cancellation protection"""
    print("\nTEST 4: Double Cancellation Protection")
    print("-" * 40)

    db = SessionLocal()
    products = setup_test_data(db)
    pepsi = products["Pepsi"]

    initial_stock = pepsi.stock

    # Create order
    order = create_order(db, OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[OrderItemCreate(product_id=pepsi.id, quantity=2)],
        discount=Decimal("0"),
        tax_rate=Decimal("0"),
        payment_method="CASH",
        amount_received=Decimal("200")
    ))

    print(f"Order created: {order.order_number}")

    # First cancellation should succeed
    first = cancel_order(db, order.id, OrderCancelIn(reason="CUSTOMER_CHANGED_ORDER"))
    assert first.status == "CANCELLED"
    print("First cancellation: SUCCESS [PASS]")

    # Second cancellation should fail
    db.refresh(pepsi)
    stock_after_first = pepsi.stock

    try:
        cancel_order(db, order.id, OrderCancelIn(reason="CUSTOMER_CHANGED_ORDER"))
        print("Second cancellation: UNEXPECTED SUCCESS [FAIL]")
        db.close()
        return False
    except Exception as e:
        if "already been cancelled" in str(e):
            print("Second cancellation: CORRECTLY REJECTED [PASS]")
        else:
            print(f"Second cancellation: WRONG ERROR {e} [FAIL]")
            db.close()
            return False

    # Verify stock was only restored once
    db.refresh(pepsi)
    stock_after_second = pepsi.stock
    assert stock_after_second == initial_stock
    assert stock_after_second == stock_after_first
    print(f"Stock only restored once: {stock_after_second} [PASS]")

    db.close()
    return True

def run_all_tests():
    """Run all Phase 8 tests"""
    print("\n" + "="*60)
    print("PHASE 8 TEST SUITE - CORE FUNCTIONALITY")
    print("="*60)

    tests = [
        test_1_single_item_cancellation,
        test_2_multi_item_cancellation,
        test_3_current_stock_incremented,
        test_4_double_cancellation_protection,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
            results.append((test.__name__, False))

    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)

    passed = sum(1 for _, r in results if r)
    failed = len(results) - passed

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{name}: {status}")

    print("-" * 60)
    print(f"Total: {passed} passed, {failed} failed")
    print("="*60)

    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
