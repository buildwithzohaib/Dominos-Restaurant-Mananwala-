"""
PHASE 9 Testing - Dashboard Endpoint
Verifies dashboard metrics are calculated correctly
"""

import sys
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.models import Product, Category, Order, OrderItem, RestaurantTable
from app.services.order_service import create_order, cancel_order
from app.schemas.schemas import OrderCreate, OrderItemCreate, OrderCancelIn
from app.services.dashboard_service import get_dashboard_overview

# Create test database
engine = create_engine("sqlite:///test_phase9_simple.db", echo=False)
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_dashboard_endpoint():
    """Test dashboard endpoint with real orders"""
    print("\nTEST: Dashboard Endpoint with Real Orders")
    print("-" * 60)

    # Use fresh database for this test
    fresh_engine = create_engine("sqlite:///test_p9_ep.db", echo=False)
    Base.metadata.drop_all(bind=fresh_engine)
    Base.metadata.create_all(bind=fresh_engine)
    FreshSession = sessionmaker(autocommit=False, autoflush=False, bind=fresh_engine)
    db = FreshSession()

    # Setup
    category = Category(name="Food", active=True)
    db.add(category)
    db.flush()

    products = []
    skus = [("Burger", "BRG-001"), ("Fries", "FRY-001"), ("Cola", "COL-001")]
    for name, sku in skus:
        p = Product(
            category_id=category.id,
            name=name,
            price=10000,
            stock=100,
            sku=sku,
            min_stock=5,
            unit="Piece",
            purchase_price=5000,
            available=True
        )
        db.add(p)
        products.append(p)

    db.commit()

    burger, fries, cola = products

    # Create 2 orders
    order1 = create_order(db, OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[
            OrderItemCreate(product_id=burger.id, quantity=2),
            OrderItemCreate(product_id=fries.id, quantity=1),
        ],
        discount=0,
        tax_rate=0,
        payment_method="CASH",
        amount_received=50000
    ))

    order2 = create_order(db, OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[
            OrderItemCreate(product_id=cola.id, quantity=3),
        ],
        discount=0,
        tax_rate=0,
        payment_method="CASH",
        amount_received=50000
    ))

    print(f"Created order 1: {order1.order_number}, Total: {order1.total}")
    print(f"Created order 2: {order2.order_number}, Total: {order2.total}")

    # Get dashboard
    dashboard = get_dashboard_overview(db)

    print(f"\nDashboard Results:")
    print(f"  Sales: Rs. {dashboard.sales}")
    print(f"  Orders: {dashboard.orders}")
    print(f"  Cancelled: {dashboard.cancelled}")
    print(f"  Low Stock Products: {dashboard.low_stock}")
    print(f"  Top Products: {len(dashboard.top_products)}")

    # Verify
    expected_sales = order1.total + order2.total
    assert dashboard.sales == expected_sales, f"Expected {expected_sales}, got {dashboard.sales}"
    assert dashboard.orders == 2, f"Expected 2 orders, got {dashboard.orders}"
    assert dashboard.cancelled == 0, f"Expected 0 cancelled, got {dashboard.cancelled}"
    assert len(dashboard.top_products) > 0, "Expected top products"

    print("\n[PASS] Dashboard endpoint working correctly")

    db.close()
    return True

def test_cancelled_orders_excluded():
    """Test that cancelled orders don't count toward sales"""
    print("\nTEST: Cancelled Orders Excluded from Dashboard")
    print("-" * 60)

    # Use fresh database for this test
    fresh_engine = create_engine("sqlite:///test_p9_co.db", echo=False)
    Base.metadata.drop_all(bind=fresh_engine)
    Base.metadata.create_all(bind=fresh_engine)
    FreshSession = sessionmaker(autocommit=False, autoflush=False, bind=fresh_engine)
    db = FreshSession()

    # Setup
    category = Category(name="Beverages", active=True)
    db.add(category)
    db.flush()

    product = Product(
        category_id=category.id,
        name="Coffee",
        price=5000,
        stock=100,
        sku="COFFEE-UNIQUE",
        min_stock=5,
        unit="Cup",
        purchase_price=2500,
        available=True
    )
    db.add(product)
    db.commit()

    # Create a paid order
    order1 = create_order(db, OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[OrderItemCreate(product_id=product.id, quantity=1)],
        discount=0,
        tax_rate=0,
        payment_method="CASH",
        amount_received=10000
    ))

    print(f"Created order 1 (PAID): {order1.order_number}")

    # Create and cancel an order
    order2 = create_order(db, OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[OrderItemCreate(product_id=product.id, quantity=5)],
        discount=0,
        tax_rate=0,
        payment_method="CASH",
        amount_received=50000
    ))

    cancel_order(db, order2.id, OrderCancelIn(reason="CUSTOMER_CHANGED_ORDER"))
    print(f"Created and cancelled order 2 (CANCELLED): {order2.order_number}")

    # Get dashboard
    dashboard = get_dashboard_overview(db)

    print(f"\nDashboard Results:")
    print(f"  Sales: Rs. {dashboard.sales} (should be only order 1)")
    print(f"  Orders: {dashboard.orders} (should be 1)")
    print(f"  Cancelled: {dashboard.cancelled} (should be 1)")

    # Verify
    assert dashboard.sales == order1.total, f"Cancelled order should not count toward sales"
    assert dashboard.orders == 1, f"Should only count PAID orders"
    assert dashboard.cancelled == 1, f"Should count 1 cancelled order"

    print("\n[PASS] Cancelled orders correctly excluded")

    db.close()
    return True

def run_all_tests():
    """Run all Phase 9 tests"""
    print("\n" + "="*60)
    print("PHASE 9 TEST SUITE - DASHBOARD")
    print("="*60)

    tests = [
        test_dashboard_endpoint,
        test_cancelled_orders_excluded,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"\n[ERROR] {e}")
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
