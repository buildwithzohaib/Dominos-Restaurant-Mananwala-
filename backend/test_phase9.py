"""
PHASE 9 Testing - Dashboard Calculations
Verifies dashboard metrics are calculated correctly from order data
"""

import sys
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.models import Product, Category, Order, OrderItem
from app.services.order_service import create_order
from app.schemas.schemas import OrderCreate, OrderItemCreate
from app.services.dashboard_service import get_dashboard_overview

# Create test database
engine = create_engine("sqlite:///test_phase9.db", echo=False)
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def setup_test_data(db):
    """Create test products and categories"""
    category = Category(name="Test Category", active=True)
    db.add(category)
    db.flush()

    products = []
    for i, (name, sku, price) in enumerate([
        ("Product A", "SKU-A", Decimal("100")),
        ("Product B", "SKU-B", Decimal("200")),
        ("Product C", "SKU-C", Decimal("150")),
    ]):
        product = Product(
            category_id=category.id,
            name=name,
            price=price,
            stock=100,
            sku=sku,
            min_stock=5,
            unit="Piece",
            purchase_price=price / 2,
            available=True
        )
        db.add(product)
        products.append(product)

    db.commit()
    for product in products:
        db.refresh(product)

    return category, products

def test_basic_dashboard_metrics():
    """Test basic dashboard metric calculations"""
    print("\nTEST: Basic Dashboard Metrics")
    print("-" * 60)

    db = SessionLocal()
    category, products = setup_test_data(db)
    product_a, product_b, product_c = products

    # Create a few orders today at different times
    # Order 1: 08:00 - 2x A, 1x B = 100*2 + 200*1 = 400
    today = datetime.utcnow().replace(hour=8, minute=0, second=0, microsecond=0)
    order1 = create_order(db, OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[
            OrderItemCreate(product_id=product_a.id, quantity=2),
            OrderItemCreate(product_id=product_b.id, quantity=1),
        ],
        discount=Decimal("0"),
        tax_rate=Decimal("0"),
        payment_method="CASH",
        amount_received=Decimal("500")
    ))
    print(f"Created order 1: {order1.order_number}, Total: {order1.total}")

    # Order 2: 12:00 - 3x C = 150*3 = 450
    order2 = create_order(db, OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[
            OrderItemCreate(product_id=product_c.id, quantity=3),
        ],
        discount=Decimal("0"),
        tax_rate=Decimal("0"),
        payment_method="CASH",
        amount_received=Decimal("500")
    ))
    print(f"Created order 2: {order2.order_number}, Total: {order2.total}")

    # Order 3: Tomorrow (should not be included in dashboard)
    tomorrow = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    order3 = Order(
        order_number="ORD-TOMORROW",
        order_type="TAKEAWAY",
        status="PAID",
        subtotal=Decimal("100"),
        discount=Decimal("0"),
        tax=Decimal("0"),
        total=Decimal("100"),
        payment_method="CASH",
        amount_received=Decimal("100"),
        change_amount=Decimal("0"),
        created_at=tomorrow
    )
    db.add(order3)
    db.add(OrderItem(
        order_id=order3.id,
        product_id=product_a.id,
        product_name="Product A",
        quantity=1,
        price=Decimal("100"),
        line_total=Decimal("100"),
    ))
    db.flush()
    db.commit()
    print(f"Created order 3 (tomorrow): {order3.order_number}")

    # Get dashboard metrics
    dashboard = get_dashboard_overview(db)

    print(f"\nDashboard Metrics:")
    print(f"  Sales: Rs. {dashboard.sales}")
    print(f"  Orders: {dashboard.orders}")
    print(f"  Cancelled: {dashboard.cancelled}")
    print(f"  Low Stock: {dashboard.low_stock}")
    print(f"  Hourly Sales (8:00): Rs. {dashboard.hourly_sales[8].revenue}")
    print(f"  Hourly Sales (12:00): Rs. {dashboard.hourly_sales[12].revenue}")

    # Verify calculations
    expected_sales = Decimal("400") + Decimal("450")  # 850
    assert dashboard.sales == expected_sales, f"Expected sales {expected_sales}, got {dashboard.sales}"
    print("[PASS] Sales calculation correct")

    assert dashboard.orders == 2, f"Expected 2 orders, got {dashboard.orders}"
    print("[PASS] Orders count correct")

    assert dashboard.cancelled == 0, f"Expected 0 cancelled, got {dashboard.cancelled}"
    print("[PASS] Cancelled count correct")

    # Note: We didn't adjust stock, so no products should be low-stock
    # All have initial stock of 100 and min_stock of 5
    assert dashboard.low_stock == 0, f"Expected 0 low stock, got {dashboard.low_stock}"
    print("[PASS] Low stock count correct")

    assert dashboard.hourly_sales[8].revenue == Decimal("400")
    assert dashboard.hourly_sales[12].revenue == Decimal("450")
    print("[PASS] Hourly sales breakdown correct")

    # Check top products
    assert len(dashboard.top_products) == 2, f"Expected 2 top products, got {len(dashboard.top_products)}"
    top1 = dashboard.top_products[0]
    assert top1.product_name == "Product A"
    assert top1.quantity_sold == 2
    print("[PASS] Top products ranking correct")

    db.close()
    return True

def test_cancelled_orders_excluded():
    """Test that cancelled orders don't count toward sales"""
    print("\nTEST: Cancelled Orders Excluded from Sales")
    print("-" * 60)

    db = SessionLocal()
    category, products = setup_test_data(db)
    product_a = products[0]

    # Create a PAID order
    order = create_order(db, OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[OrderItemCreate(product_id=product_a.id, quantity=1)],
        discount=Decimal("0"),
        tax_rate=Decimal("0"),
        payment_method="CASH",
        amount_received=Decimal("200")
    ))

    # Manually create a CANCELLED order
    cancelled_order = Order(
        order_number="ORD-CANCELLED",
        order_type="TAKEAWAY",
        status="CANCELLED",
        subtotal=Decimal("100"),
        discount=Decimal("0"),
        tax=Decimal("0"),
        total=Decimal("100"),
        payment_method="CASH",
        amount_received=Decimal("100"),
        change_amount=Decimal("0"),
        cancelled_at=datetime.utcnow(),
        cancelled_reason="Test"
    )
    db.add(cancelled_order)
    db.flush()

    # Add order item to cancelled order
    db.add(OrderItem(
        order_id=cancelled_order.id,
        product_id=product_a.id,
        product_name="Product A",
        quantity=5,
        price=Decimal("100"),
        line_total=Decimal("500"),
    ))
    db.commit()

    dashboard = get_dashboard_overview(db)

    # Should only count the PAID order
    assert dashboard.sales == order.total
    assert dashboard.orders == 1
    assert dashboard.cancelled == 1
    print("[PASS] Cancelled orders correctly excluded from sales")
    print(f"  Sales: Rs. {dashboard.sales} (only 1 order)")
    print(f"  Cancelled: {dashboard.cancelled}")

    db.close()
    return True

def test_low_stock_detection():
    """Test low stock product detection"""
    print("\nTEST: Low Stock Detection")
    print("-" * 60)

    db = SessionLocal()

    category = Category(name="Category", active=True)
    db.add(category)
    db.flush()

    # Create products with different stock levels
    products = [
        Product(
            category_id=category.id,
            name="In Stock",
            price=Decimal("100"),
            stock=100,
            sku="IN-STOCK",
            min_stock=5,
            unit="Piece",
            purchase_price=Decimal("50"),
            available=True
        ),
        Product(
            category_id=category.id,
            name="Low Stock",
            price=Decimal("100"),
            stock=3,
            sku="LOW-STOCK",
            min_stock=5,
            unit="Piece",
            purchase_price=Decimal("50"),
            available=True
        ),
        Product(
            category_id=category.id,
            name="Out of Stock",
            price=Decimal("100"),
            stock=0,
            sku="OUT-OF-STOCK",
            min_stock=5,
            unit="Piece",
            purchase_price=Decimal("50"),
            available=True
        ),
        Product(
            category_id=category.id,
            name="Disabled",
            price=Decimal("100"),
            stock=0,
            sku="DISABLED",
            min_stock=5,
            unit="Piece",
            purchase_price=Decimal("50"),
            available=False  # Disabled products shouldn't count
        ),
    ]

    for p in products:
        db.add(p)

    db.commit()

    dashboard = get_dashboard_overview(db)

    # Should count 2 low/out-of-stock products (not the disabled one)
    assert dashboard.low_stock == 2, f"Expected 2 low stock, got {dashboard.low_stock}"
    print("[PASS] Low stock detection correct")
    print(f"  Low/Out-of-Stock: {dashboard.low_stock} (excluded disabled products)")

    db.close()
    return True

def run_all_tests():
    """Run all Phase 9 dashboard tests"""
    print("\n" + "="*60)
    print("PHASE 9 TEST SUITE - DASHBOARD CALCULATIONS")
    print("="*60)

    tests = [
        test_basic_dashboard_metrics,
        test_cancelled_orders_excluded,
        test_low_stock_detection,
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
