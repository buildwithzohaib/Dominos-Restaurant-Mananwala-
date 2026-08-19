"""
PHASE 9 Testing - Dashboard Calculations
Verifies dashboard metrics are calculated correctly from order data
"""

import sys
from datetime import datetime, timedelta, timezone
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.models import Product, Category, Order, OrderItem, Settings
from app.services.order_service import create_order
from app.schemas.schemas import OrderCreate, OrderItemCreate
from app.services.dashboard_service import get_dashboard_overview
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

def setup_test_data(db):
    """Create test products and categories"""
    category = Category(
        name_raw="Test Category",
        name_display=normalize_display("Test Category"),
        name_key=derive_key("Test Category"),
        active=True
    )
    db.add(category)
    db.flush()

    products = []
    for i, (name, sku, price) in enumerate([
        ("Product A", "SKU-A", 10000),
        ("Product B", "SKU-B", 20000),
        ("Product C", "SKU-C", 15000),
    ]):
        product = Product(
            category_id=category.id,
            name_raw=name,
            name_display=normalize_display(name),
            name_key=derive_key(name),
            price=price,
            stock=100,
            sku=sku,
            min_stock=5,
            unit="Piece",
            purchase_price=price // 2,
            available=True
        )
        db.add(product)
        products.append(product)

    db.commit()
    for product in products:
        db.refresh(product)

    return category, products

def test_basic_dashboard_metrics(db_session):
    """Test basic dashboard metric calculations"""
    print("\nTEST: Basic Dashboard Metrics")
    print("-" * 60)

    db = db_session
    category, products = setup_test_data(db)
    product_a, product_b, product_c = products

    # Create a few orders today at different times
    # Order 1: 08:00 - 2x A, 1x B = 10000*2 + 20000*1 = 40000
    today = datetime.utcnow().replace(hour=8, minute=0, second=0, microsecond=0)
    order1 = create_order(db, OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[
            OrderItemCreate(product_id=product_a.id, quantity=2),
            OrderItemCreate(product_id=product_b.id, quantity=1),
        ],
        discount=0,
        tax_rate=0,
        payment_method="CASH",
        amount_received=50000
    ))
    # Update both created_at and paid_at to match the test time, since dashboard now uses paid_at
    db.query(Order).filter(Order.id == order1.id).update({"created_at": today, "paid_at": today})
    db.commit()
    print(f"Created order 1: {order1.order_number}, Total: {order1.total}")

    # Order 2: 12:00 - 3x C = 15000*3 = 45000
    order2_time = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
    order2 = create_order(db, OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[
            OrderItemCreate(product_id=product_c.id, quantity=3),
        ],
        discount=0,
        tax_rate=0,
        payment_method="CASH",
        amount_received=50000
    ))
    # Update both created_at and paid_at to match the test time, since dashboard now uses paid_at
    db.query(Order).filter(Order.id == order2.id).update({"created_at": order2_time, "paid_at": order2_time})
    db.commit()
    print(f"Created order 2: {order2.order_number}, Total: {order2.total}")

    # Order 3: Tomorrow at or after day_starts_at (should not be included in dashboard)
    # Business day runs from today 06:00 to tomorrow 06:00, so order3 must be at/after tomorrow 06:00
    tomorrow = datetime.utcnow().replace(hour=6, minute=0, second=1, microsecond=0) + timedelta(days=1)
    order3 = Order(
        order_number="ORD-TOMORROW",
        order_type="TAKEAWAY",
        status="PAID",
        subtotal=10000,
        discount=0,
        tax=0,
        total=10000,
        payment_method="CASH",
        amount_received=10000,
        change_amount=0,
        created_at=tomorrow,
        paid_at=tomorrow  # Set paid_at to tomorrow, matching created_at
    )
    db.add(order3)
    db.flush()
    db.add(OrderItem(
        order_id=order3.id,
        product_id=product_a.id,
        product_name="Product A",
        quantity=1,
        price=10000,
        line_total=10000,
    ))
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
    expected_sales = 40000 + 45000  # 850 rupees
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

    assert dashboard.hourly_sales[8].revenue == 40000
    assert dashboard.hourly_sales[12].revenue == 45000
    print("[PASS] Hourly sales breakdown correct")

    # Check top products (ordered by quantity_sold descending)
    # Order 1: 2x A, 1x B = A:qty=2, B:qty=1
    # Order 2: 3x C = C:qty=3
    # Expected ranking: C (3), A (2), B (1)
    assert len(dashboard.top_products) == 3, f"Expected 3 top products, got {len(dashboard.top_products)}"
    top1 = dashboard.top_products[0]
    assert top1.product_name == "Product C"
    assert top1.quantity_sold == 3
    assert top1.revenue == 45000
    top2 = dashboard.top_products[1]
    assert top2.product_name == "Product A"
    assert top2.quantity_sold == 2
    assert top2.revenue == 20000
    top3 = dashboard.top_products[2]
    assert top3.product_name == "Product B"
    assert top3.quantity_sold == 1
    assert top3.revenue == 20000
    print("[PASS] Top products ranking correct")

def test_cancelled_orders_excluded(db_session):
    """Test that cancelled orders don't count toward sales"""
    print("\nTEST: Cancelled Orders Excluded from Sales")
    print("-" * 60)

    db = db_session
    category, products = setup_test_data(db)
    product_a = products[0]

    # Create a PAID order
    order = create_order(db, OrderCreate(
        order_type="TAKEAWAY",
        table_id=None,
        items=[OrderItemCreate(product_id=product_a.id, quantity=1)],
        discount=0,
        tax_rate=0,
        payment_method="CASH",
        amount_received=20000
    ))

    # Manually create a CANCELLED order
    cancelled_order = Order(
        order_number="ORD-CANCELLED",
        order_type="TAKEAWAY",
        status="CANCELLED",
        subtotal=10000,
        discount=0,
        tax=0,
        total=10000,
        payment_method="CASH",
        amount_received=10000,
        change_amount=0,
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
        price=10000,
        line_total=50000,
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

def test_low_stock_detection(db_session):
    """Test low stock product detection"""
    print("\nTEST: Low Stock Detection")
    print("-" * 60)

    db = db_session

    category = Category(
        name_raw="Category",
        name_display=normalize_display("Category"),
        name_key=derive_key("Category"),
        active=True
    )
    db.add(category)
    db.flush()

    # Create products with different stock levels
    products = [
        Product(
            category_id=category.id,
            name_raw="In Stock",
            name_display=normalize_display("In Stock"),
            name_key=derive_key("In Stock"),
            price=10000,
            stock=100,
            sku="IN-STOCK",
            min_stock=5,
            unit="Piece",
            purchase_price=5000,
            available=True
        ),
        Product(
            category_id=category.id,
            name_raw="Low Stock",
            name_display=normalize_display("Low Stock"),
            name_key=derive_key("Low Stock"),
            price=10000,
            stock=3,
            sku="LOW-STOCK",
            min_stock=5,
            unit="Piece",
            purchase_price=5000,
            available=True
        ),
        Product(
            category_id=category.id,
            name_raw="Out of Stock",
            name_display=normalize_display("Out of Stock"),
            name_key=derive_key("Out of Stock"),
            price=10000,
            stock=0,
            sku="OUT-OF-STOCK",
            min_stock=5,
            unit="Piece",
            purchase_price=5000,
            available=True
        ),
        Product(
            category_id=category.id,
            name_raw="Disabled",
            name_display=normalize_display("Disabled"),
            name_key=derive_key("Disabled"),
            price=10000,
            stock=0,
            sku="DISABLED",
            min_stock=5,
            unit="Piece",
            purchase_price=5000,
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

def test_business_day_after_boundary(db_session):
    """Test dashboard boundary when current time is AFTER day_starts_at (default 06:00)"""
    print("\nTEST: Business Day After Boundary (06:00)")
    print("-" * 60)

    db = db_session
    category, products = setup_test_data(db)
    product_a = products[0]

    # Ensure settings with default day_starts_at (06:00)
    settings = db.query(Settings).first()
    if not settings:
        settings = Settings(day_starts_at="06:00")
        db.add(settings)
    else:
        settings.day_starts_at = "06:00"
    db.commit()

    # Simulate: current time is 2026-08-19 14:00 (after 06:00 boundary)
    # Business day should run from 2026-08-19 06:00 to 2026-08-20 06:00
    # Use naive datetimes (matching what database stores)
    now = datetime(2026, 8, 19, 14, 0, 0)
    boundary_start = datetime(2026, 8, 19, 6, 0, 0)
    boundary_end = datetime(2026, 8, 20, 6, 0, 0)

    # Order paid AT the boundary (06:00) — should be included
    order_at_boundary = Order(
        order_number="ORD-BOUNDARY",
        order_type="TAKEAWAY",
        status="PAID",
        subtotal=10000,
        discount=0,
        tax=0,
        total=10000,
        payment_method="CASH",
        amount_received=10000,
        change_amount=0,
        created_at=boundary_start,
        paid_at=boundary_start,
    )
    db.add(order_at_boundary)
    db.flush()
    db.add(OrderItem(
        order_id=order_at_boundary.id,
        product_id=product_a.id,
        product_name="Product A",
        quantity=1,
        price=10000,
        line_total=10000,
    ))

    # Order paid after boundary (14:00) — should be included
    order_after_boundary = Order(
        order_number="ORD-AFTER",
        order_type="TAKEAWAY",
        status="PAID",
        subtotal=10000,
        discount=0,
        tax=0,
        total=10000,
        payment_method="CASH",
        amount_received=10000,
        change_amount=0,
        created_at=now,
        paid_at=now,
    )
    db.add(order_after_boundary)
    db.flush()
    db.add(OrderItem(
        order_id=order_after_boundary.id,
        product_id=product_a.id,
        product_name="Product A",
        quantity=1,
        price=10000,
        line_total=10000,
    ))

    # Order paid BEFORE boundary (05:00 on same day) — should NOT be included
    order_before_boundary = Order(
        order_number="ORD-BEFORE",
        order_type="TAKEAWAY",
        status="PAID",
        subtotal=10000,
        discount=0,
        tax=0,
        total=10000,
        payment_method="CASH",
        amount_received=10000,
        change_amount=0,
        created_at=boundary_start - timedelta(hours=1),
        paid_at=boundary_start - timedelta(hours=1),
    )
    db.add(order_before_boundary)
    db.flush()
    db.add(OrderItem(
        order_id=order_before_boundary.id,
        product_id=product_a.id,
        product_name="Product A",
        quantity=1,
        price=10000,
        line_total=10000,
    ))
    db.commit()

    # Mock the current time for get_dashboard_overview
    from app.utils.dates import get_business_day_boundaries
    start, end = get_business_day_boundaries(db, now)

    print(f"Current time: {now}")
    print(f"Day starts at: 06:00")
    print(f"Business day: {start} to {end}")

    assert start == boundary_start, f"Expected start {boundary_start}, got {start}"
    assert end == boundary_end, f"Expected end {boundary_end}, got {end}"
    print("[PASS] Business day boundary correct (after 06:00)")

def test_business_day_before_boundary(db_session):
    """Test dashboard boundary when current time is BEFORE day_starts_at (custom 14:00)"""
    print("\nTEST: Business Day Before Boundary (14:00)")
    print("-" * 60)

    db = db_session
    category, products = setup_test_data(db)
    product_a = products[0]

    # Set a custom day_starts_at (14:00)
    settings = db.query(Settings).first()
    if not settings:
        settings = Settings(day_starts_at="14:00")
        db.add(settings)
    else:
        settings.day_starts_at = "14:00"
    db.commit()

    # Simulate: current time is 2026-08-19 10:00 (BEFORE 14:00 boundary)
    # Business day should run from 2026-08-18 14:00 to 2026-08-19 14:00
    # Use naive datetimes (matching what database stores)
    now = datetime(2026, 8, 19, 10, 0, 0)
    boundary_start = datetime(2026, 8, 18, 14, 0, 0)
    boundary_end = datetime(2026, 8, 19, 14, 0, 0)

    # Order paid before boundary (from yesterday afternoon) — should be included
    order_from_yesterday = Order(
        order_number="ORD-YESTERDAY",
        order_type="TAKEAWAY",
        status="PAID",
        subtotal=10000,
        discount=0,
        tax=0,
        total=10000,
        payment_method="CASH",
        amount_received=10000,
        change_amount=0,
        created_at=boundary_start,
        paid_at=boundary_start,
    )
    db.add(order_from_yesterday)
    db.flush()
    db.add(OrderItem(
        order_id=order_from_yesterday.id,
        product_id=product_a.id,
        product_name="Product A",
        quantity=1,
        price=10000,
        line_total=10000,
    ))

    # Order paid today before boundary (10:00) — should be included
    order_today_before_boundary = Order(
        order_number="ORD-TODAY-BEFORE",
        order_type="TAKEAWAY",
        status="PAID",
        subtotal=10000,
        discount=0,
        tax=0,
        total=10000,
        payment_method="CASH",
        amount_received=10000,
        change_amount=0,
        created_at=now,
        paid_at=now,
    )
    db.add(order_today_before_boundary)
    db.flush()
    db.add(OrderItem(
        order_id=order_today_before_boundary.id,
        product_id=product_a.id,
        product_name="Product A",
        quantity=1,
        price=10000,
        line_total=10000,
    ))

    # Order paid today AFTER boundary (15:00) — should NOT be included
    order_after_boundary = Order(
        order_number="ORD-AFTER-BOUNDARY",
        order_type="TAKEAWAY",
        status="PAID",
        subtotal=10000,
        discount=0,
        tax=0,
        total=10000,
        payment_method="CASH",
        amount_received=10000,
        change_amount=0,
        created_at=boundary_end + timedelta(hours=1),
        paid_at=boundary_end + timedelta(hours=1),
    )
    db.add(order_after_boundary)
    db.flush()
    db.add(OrderItem(
        order_id=order_after_boundary.id,
        product_id=product_a.id,
        product_name="Product A",
        quantity=1,
        price=10000,
        line_total=10000,
    ))
    db.commit()

    # Test the boundary calculation
    from app.utils.dates import get_business_day_boundaries
    start, end = get_business_day_boundaries(db, now)

    print(f"Current time: {now}")
    print(f"Day starts at: 14:00")
    print(f"Business day: {start} to {end}")

    assert start == boundary_start, f"Expected start {boundary_start}, got {start}"
    assert end == boundary_end, f"Expected end {boundary_end}, got {end}"
    print("[PASS] Business day boundary correct (before 14:00)")

def run_all_tests():
    """Run all Phase 9 dashboard tests"""
    print("\n" + "="*60)
    print("PHASE 9 TEST SUITE - DASHBOARD CALCULATIONS")
    print("="*60)

    tests = [
        test_basic_dashboard_metrics,
        test_cancelled_orders_excluded,
        test_low_stock_detection,
        test_business_day_after_boundary,
        test_business_day_before_boundary,
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
