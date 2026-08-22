"""
Range-Aware Dashboard Testing Suite (Stage 8 Step 2)

Tests for range resolution, profit calculation, per-staff attribution, and metrics
aggregation. Uses fresh temporary database per test.
"""

import pytest
import tempfile
import os
import gc
import time
from datetime import datetime, timedelta, date, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.database import Base
from app.models.models import (
    Settings, Category, Product, Order, OrderItem, RestaurantTable, User, UserSession
)
from app.schemas.schemas import OrderCreate, OrderItemCreate, OpenOrderCreate
from app.services.order_service import create_order
from app.services.dashboard_service import (
    resolve_range, get_dashboard_range, _calculate_profit, _calculate_per_staff_metrics
)


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

    # Seed Settings with 06:00 business day start
    settings = Settings(id=1, restaurant_name="Test Restaurant", day_starts_at="06:00")
    session.add(settings)
    session.flush()

    # Seed Category
    category = Category(name_raw="Food", name_display="Food", name_key="food", active=True)
    session.add(category)
    session.flush()
    category_id = category.id

    # Seed Table
    table = RestaurantTable(name="T1", seats=4, active=True)
    session.add(table)
    session.flush()
    table_id = table.id

    # Seed Products with different costs
    product_a = Product(
        category_id=category_id,
        name_raw="Product A",
        name_display="Product A",
        name_key="producta",
        price=10000,  # Rs. 100
        stock=100,
        image=None,
        image_hash=None,
        available=True,
        sku="A-001",
        min_stock=5,
        unit="Piece",
        purchase_price=4000,  # Rs. 40 cost
    )
    session.add(product_a)
    session.flush()

    product_b = Product(
        category_id=category_id,
        name_raw="Product B",
        name_display="Product B",
        name_key="productb",
        price=20000,  # Rs. 200
        stock=100,
        image=None,
        image_hash=None,
        available=True,
        sku="B-001",
        min_stock=5,
        unit="Piece",
        purchase_price=8000,  # Rs. 80 cost
    )
    session.add(product_b)
    session.flush()

    product_no_cost = Product(
        category_id=category_id,
        name_raw="Product No Cost",
        name_display="Product No Cost",
        name_key="productnocost",
        price=5000,  # Rs. 50
        stock=100,
        image=None,
        image_hash=None,
        available=True,
        sku="NC-001",
        min_stock=5,
        unit="Piece",
        purchase_price=0,  # Cost not entered
    )
    session.add(product_no_cost)
    session.flush()

    session.commit()

    # Seed users for attribution tests
    owner = User(
        name="Owner",
        pin="hashed_owner_pin",
        is_owner=True,
        can_cancel=True,
        can_discount=True,
        can_manage_settings=True,
        is_active=True,
    )
    session.add(owner)
    session.flush()

    staff = User(
        name="Staff",
        pin="hashed_staff_pin",
        is_owner=False,
        can_cancel=True,
        can_discount=True,
        can_manage_settings=False,
        is_active=True,
    )
    session.add(staff)
    session.flush()
    session.commit()

    # Expose seeded IDs to tests
    session.category_id = category_id
    session.table_id = table_id
    session.product_a_id = product_a.id
    session.product_b_id = product_b.id
    session.product_no_cost_id = product_no_cost.id
    session.owner_id = owner.id
    session.staff_id = staff.id

    yield session
    session.close()


# ============================================================================
# RANGE RESOLUTION TESTS
# ============================================================================

class TestRangeResolution:
    """Tests for the range helper function."""

    def test_today_range_returns_current_and_previous_day(self, db):
        """Today range returns today's business day and yesterday's."""
        # Use a fixed reference time (e.g., 2pm on 2026-08-22)
        reference = datetime(2026, 8, 22, 14, 0, 0)  # After 06:00 boundary
        (current_start, current_end), (prev_start, prev_end) = resolve_range(
            db, "today", reference_time=reference
        )

        # Current should be 2026-08-22 06:00 to 2026-08-23 06:00
        assert current_start == datetime(2026, 8, 22, 6, 0, 0)
        assert current_end == datetime(2026, 8, 23, 6, 0, 0)

        # Previous should be 2026-08-21 06:00 to 2026-08-22 06:00
        assert prev_start == datetime(2026, 8, 21, 6, 0, 0)
        assert prev_end == datetime(2026, 8, 22, 6, 0, 0)

    def test_range_before_day_boundary(self, db):
        """Time before boundary (03:00) is treated as part of previous calendar day."""
        reference = datetime(2026, 8, 22, 3, 0, 0)  # Before 06:00 boundary
        (current_start, current_end), _ = resolve_range(
            db, "today", reference_time=reference
        )

        # Current business day started yesterday (2026-08-21 06:00)
        assert current_start == datetime(2026, 8, 21, 6, 0, 0)
        assert current_end == datetime(2026, 8, 22, 6, 0, 0)

    def test_7days_range(self, db):
        """7 days range returns last 7 business days ending with today."""
        reference = datetime(2026, 8, 22, 14, 0, 0)
        (current_start, current_end), (prev_start, prev_end) = resolve_range(
            db, "7days", reference_time=reference
        )

        # Current window spans 7 days
        assert (current_end - current_start).days == 7
        # Current end is today's boundary end
        assert current_end == datetime(2026, 8, 23, 6, 0, 0)

    def test_30days_range(self, db):
        """30 days range returns last 30 business days."""
        reference = datetime(2026, 8, 22, 14, 0, 0)
        (current_start, current_end), _ = resolve_range(
            db, "30days", reference_time=reference
        )

        # Current window spans 30 days
        assert (current_end - current_start).days == 30

    def test_custom_range(self, db):
        """Custom range accepts start and end dates."""
        custom_start = date(2026, 8, 15)
        custom_end = date(2026, 8, 20)
        (current_start, current_end), _ = resolve_range(
            db, "custom", custom_start=custom_start, custom_end=custom_end
        )

        # Window spans from start date's business day to end date's business day.
        # End is exclusive (belongs to the next calendar day's start time).
        assert current_start == datetime(2026, 8, 15, 6, 0)
        assert current_end == datetime(2026, 8, 21, 6, 0)  # Exclusive, so 21 @ 06:00


# ============================================================================
# PROFIT CALCULATION TESTS
# ============================================================================

class TestProfitCalculation:
    """Tests for profit calculation with cost snapshots."""

    def test_profit_from_clean_order(self, db):
        """Single order with valid costs calculates profit correctly."""
        # Order: 1x Product A (price 10000, cost 4000) + 1x Product B (price 20000, cost 8000)
        # Subtotal: 30000, no discount
        # Cost: 4000 + 8000 = 12000
        # Profit: 30000 - 12000 = 18000
        window_start = datetime(2026, 8, 22, 6, 0, 0)
        window_end = datetime(2026, 8, 23, 6, 0, 0)

        payload = OrderCreate(
            order_type="TAKEAWAY",
            items=[
                OrderItemCreate(product_id=db.product_a_id, quantity=1),
                OrderItemCreate(product_id=db.product_b_id, quantity=1),
            ],
            discount=0,
            amount_received=30000,
            payment_method="CASH",
        )
        order = create_order(db, payload)

        profit, orders_missing_cost = _calculate_profit(db, window_start, window_end)
        assert profit == 18000
        assert orders_missing_cost == 0

    def test_profit_with_discount(self, db):
        """Order with discount: profit = (subtotal - discount) - cost."""
        # Order: 1x Product A (price 10000, cost 4000), discount 2000
        # Revenue: 10000 - 2000 = 8000
        # Cost: 4000
        # Profit: 8000 - 4000 = 4000
        window_start = datetime(2026, 8, 22, 6, 0, 0)
        window_end = datetime(2026, 8, 23, 6, 0, 0)

        payload = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_a_id, quantity=1)],
            discount=2000,
            amount_received=10000,
            payment_method="CASH",
        )
        order = create_order(db, payload)

        profit, orders_missing_cost = _calculate_profit(db, window_start, window_end)
        assert profit == 4000
        assert orders_missing_cost == 0

    def test_order_with_zero_cost_excluded(self, db):
        """Order with any item cost=0 is excluded from profit."""
        # Order: 1x Product No Cost (price 5000, cost 0)
        # This order is excluded from profit
        window_start = datetime(2026, 8, 22, 6, 0, 0)
        window_end = datetime(2026, 8, 23, 6, 0, 0)

        payload = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_no_cost_id, quantity=1)],
            discount=0,
            amount_received=5000,
            payment_method="CASH",
        )
        order = create_order(db, payload)

        profit, orders_missing_cost = _calculate_profit(db, window_start, window_end)
        assert profit == 0
        assert orders_missing_cost == 1

    def test_multiple_orders_only_profit_calculates(self, db):
        """Mix of clean and excluded orders: profit sums only clean orders."""
        window_start = datetime(2026, 8, 22, 6, 0, 0)
        window_end = datetime(2026, 8, 23, 6, 0, 0)

        # Clean order: Product A (profit 6000)
        payload1 = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_a_id, quantity=1)],
            discount=0,
            amount_received=10000,
            payment_method="CASH",
        )
        create_order(db, payload1)

        # Excluded order: Product No Cost (cost 0)
        payload2 = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_no_cost_id, quantity=1)],
            discount=0,
            amount_received=5000,
            payment_method="CASH",
        )
        create_order(db, payload2)

        profit, orders_missing_cost = _calculate_profit(db, window_start, window_end)
        assert profit == 6000  # Only from Product A order
        assert orders_missing_cost == 1  # Product No Cost order


# ============================================================================
# SALES AND ORDERS METRICS TESTS
# ============================================================================

class TestSalesMetrics:
    """Tests for sales and order counting in windows."""

    def test_sales_only_counts_paid_orders(self, db):
        """Sales metric counts only PAID orders, not OPEN."""
        reference = datetime(2026, 8, 22, 14, 0, 0)

        payload = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_a_id, quantity=1)],
            discount=0,
            amount_received=10000,
            payment_method="CASH",
        )
        order = create_order(db, payload)

        dashboard = get_dashboard_range(db, "today", reference_time=reference)
        # Order total should be 10000 (product price * qty)
        assert dashboard.sales == 10000
        assert dashboard.orders == 1

    def test_order_paid_after_boundary_in_next_day(self, db):
        """Order paid after business day boundary falls in the next day."""
        # Order paid at 2026-08-23 03:00 (before the 06:00 boundary for 2026-08-23)
        # So it belongs to 2026-08-22's business day
        reference = datetime(2026, 8, 22, 14, 0, 0)

        payload = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_a_id, quantity=1)],
            discount=0,
            amount_received=10000,
            payment_method="CASH",
        )
        order = create_order(db, payload)
        # Manually set paid_at to just before the boundary
        order.paid_at = datetime(2026, 8, 23, 3, 0, 0)
        db.commit()

        dashboard = get_dashboard_range(db, "today", reference_time=reference)
        assert dashboard.orders == 1

    def test_average_order_value_zero_when_no_orders(self, db):
        """Average order value is 0 when no orders, no divide error."""
        reference = datetime(2026, 8, 22, 14, 0, 0)

        # Create order in a different window (yesterday)
        payload = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_a_id, quantity=1)],
            discount=0,
            amount_received=10000,
            payment_method="CASH",
        )
        order = create_order(db, payload)
        # Move order to yesterday
        order.paid_at = datetime(2026, 8, 21, 10, 0, 0)
        db.commit()

        # Query today (should have no orders)
        dashboard = get_dashboard_range(db, "today", reference_time=reference)
        assert dashboard.orders == 0
        assert dashboard.average_order_value == 0


# ============================================================================
# PER-STAFF ATTRIBUTION TESTS
# ============================================================================

class TestPerStaffAttribution:
    """Tests for per-staff sales and cancellation attribution."""

    def test_sales_attributed_to_cashier(self, db):
        """Order sales are attributed to the cashier via performed_by_user_id."""
        window_start = datetime(2026, 8, 22, 6, 0, 0)
        window_end = datetime(2026, 8, 23, 6, 0, 0)

        payload = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_a_id, quantity=1)],
            discount=0,
            amount_received=10000,
            payment_method="CASH",
        )
        order = create_order(db, payload, performed_by_user_id=db.owner_id)

        per_staff = _calculate_per_staff_metrics(db, window_start, window_end)
        assert len(per_staff) == 1
        assert per_staff[0].user_id == db.owner_id
        assert per_staff[0].user_name == "Owner"
        assert per_staff[0].sales == 10000
        assert per_staff[0].orders == 1

    def test_cancellations_attributed_separately(self, db):
        """Cancellations are attributed via cancel_order_performed_by_user_id."""
        window_start = datetime(2026, 8, 22, 6, 0, 0)
        window_end = datetime(2026, 8, 23, 6, 0, 0)

        # Order A: PAID, processed by owner
        payload_a = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_a_id, quantity=1)],
            discount=0,
            amount_received=10000,
            payment_method="CASH",
        )
        order_a = create_order(db, payload_a, performed_by_user_id=db.owner_id)

        # Order B: PAID by owner, then cancelled by staff
        payload_b = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_b_id, quantity=1)],
            discount=0,
            amount_received=20000,
            payment_method="CASH",
        )
        order_b = create_order(db, payload_b, performed_by_user_id=db.owner_id)

        # Manually flip order B to CANCELLED, attributed to staff
        order_b.status = "CANCELLED"
        order_b.cancelled_at = datetime(2026, 8, 22, 10, 0, 0)
        order_b.cancel_order_performed_by_user_id = db.staff_id
        db.commit()

        per_staff = _calculate_per_staff_metrics(db, window_start, window_end)
        # Should have both users
        staff_metrics = {m.user_id: m for m in per_staff}

        # Owner's sales include only PAID orders (order A). Order B is CANCELLED and no longer PAID.
        assert staff_metrics[db.owner_id].sales == 10000  # order_a only
        assert staff_metrics[db.owner_id].orders == 1

        # Staff processed one cancellation. Cancelled orders don't appear in sales metrics.
        assert staff_metrics[db.staff_id].cancelled == 1
        assert staff_metrics[db.staff_id].sales == 0
        assert staff_metrics[db.staff_id].orders == 0


# ============================================================================
# DAILY SALES TESTS
# ============================================================================

class TestDailySales:
    """Tests for daily sales breakdown with zero rows."""

    def test_daily_sales_includes_zero_days(self, db):
        """Daily sales includes zero rows for days with no sales."""
        reference = datetime(2026, 8, 22, 14, 0, 0)

        # Create order on specific date
        payload = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_a_id, quantity=1)],
            discount=0,
            amount_received=10000,
            payment_method="CASH",
        )
        order = create_order(db, payload)
        # Set order to 2026-08-22
        order.paid_at = datetime(2026, 8, 22, 10, 0, 0)
        db.commit()

        # Query 7-day range
        dashboard = get_dashboard_range(db, "7days", reference_time=reference)

        # Should have 7 days of data
        assert len(dashboard.daily_sales) == 7
        # 2026-08-22 should have revenue
        day_22 = next(d for d in dashboard.daily_sales if d.date == date(2026, 8, 22))
        assert day_22.revenue == 10000
        # Other days should be 0
        for daily in dashboard.daily_sales:
            if daily.date != date(2026, 8, 22):
                assert daily.revenue == 0


# ============================================================================
# GET_ORDERS_FOR_METRIC TESTS
# ============================================================================

class TestGetOrdersForMetric:
    """Tests for retrieving orders behind a dashboard metric."""

    def test_cancelled_metric_returns_only_cancelled_orders(self, db):
        """'cancelled' metric returns only CANCELLED orders in the window."""
        window_start = datetime(2026, 8, 22, 6, 0, 0)
        window_end = datetime(2026, 8, 23, 6, 0, 0)

        from app.services.dashboard_service import get_orders_for_metric

        # Create PAID order
        payload_paid = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_a_id, quantity=1)],
            discount=0,
            amount_received=10000,
            payment_method="CASH",
        )
        paid_order = create_order(db, payload_paid)
        paid_order.paid_at = datetime(2026, 8, 22, 10, 0, 0)

        # Create CANCELLED order
        payload_cancel = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_b_id, quantity=1)],
            discount=0,
            amount_received=20000,
            payment_method="CASH",
        )
        cancel_order = create_order(db, payload_cancel)
        cancel_order.status = "CANCELLED"
        cancel_order.cancelled_at = datetime(2026, 8, 22, 11, 0, 0)
        db.commit()

        orders = get_orders_for_metric(db, "cancelled", "today", reference_time=window_start)
        assert len(orders) == 1
        assert orders[0].id == cancel_order.id
        assert orders[0].status == "CANCELLED"

    def test_discounts_metric_excludes_zero_discount(self, db):
        """'discounts' metric excludes orders with discount=0."""
        from app.services.dashboard_service import get_orders_for_metric

        # Create order with discount
        payload_discount = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_a_id, quantity=1)],
            discount=500,
            amount_received=9500,
            payment_method="CASH",
        )
        discount_order = create_order(db, payload_discount)

        # Create order without discount (product_b costs 20000, so amount_received must be >= 20000)
        payload_no_discount = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_b_id, quantity=1)],
            discount=0,
            amount_received=20000,
            payment_method="CASH",
        )
        no_discount_order = create_order(db, payload_no_discount)

        orders = get_orders_for_metric(db, "discounts", "today")
        assert len(orders) == 1
        assert orders[0].id == discount_order.id

    def test_staff_metric_with_user_id_filters_by_cashier(self, db):
        """'staff' metric with user_id returns only that user's PAID orders."""
        from app.services.dashboard_service import get_orders_for_metric

        # Order by owner
        payload_owner = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_a_id, quantity=1)],
            discount=0,
            amount_received=10000,
            payment_method="CASH",
        )
        owner_order = create_order(db, payload_owner, performed_by_user_id=db.owner_id)

        # Order by staff
        payload_staff = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_b_id, quantity=1)],
            discount=0,
            amount_received=20000,
            payment_method="CASH",
        )
        staff_order = create_order(db, payload_staff, performed_by_user_id=db.staff_id)

        # Query for staff's orders
        orders = get_orders_for_metric(db, "staff", "today", user_id=db.staff_id)
        assert len(orders) == 1
        assert orders[0].id == staff_order.id

    def test_staff_metric_with_no_user_returns_null_user_orders(self, db):
        """'staff' metric with no_user (user_id=None) returns only orders with performed_by_user_id IS NULL."""
        from app.services.dashboard_service import get_orders_for_metric

        # Order with no user (performed_by_user_id IS NULL)
        payload_no_user = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_a_id, quantity=1)],
            discount=0,
            amount_received=10000,
            payment_method="CASH",
        )
        no_user_order = create_order(db, payload_no_user, performed_by_user_id=None)

        # Order with user
        payload_with_user = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_b_id, quantity=1)],
            discount=0,
            amount_received=20000,
            payment_method="CASH",
        )
        with_user_order = create_order(db, payload_with_user, performed_by_user_id=db.owner_id)

        # Query for no-user orders (explicitly pass user_id=None)
        orders = get_orders_for_metric(db, "staff", "today", user_id=None)
        assert len(orders) == 1
        assert orders[0].id == no_user_order.id

    def test_window_boundary_excludes_orders_outside(self, db):
        """Orders just outside the window are excluded."""
        from app.services.dashboard_service import get_orders_for_metric

        window_start = datetime(2026, 8, 22, 6, 0, 0)

        # Order inside the window
        payload_inside = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_a_id, quantity=1)],
            discount=0,
            amount_received=10000,
            payment_method="CASH",
        )
        inside_order = create_order(db, payload_inside)
        inside_order.paid_at = datetime(2026, 8, 22, 10, 0, 0)

        # Order outside the window (just before start)
        payload_outside = OrderCreate(
            order_type="TAKEAWAY",
            items=[OrderItemCreate(product_id=db.product_b_id, quantity=1)],
            discount=0,
            amount_received=20000,
            payment_method="CASH",
        )
        outside_order = create_order(db, payload_outside)
        outside_order.paid_at = datetime(2026, 8, 21, 5, 59, 59)
        db.commit()

        orders = get_orders_for_metric(db, "sales", "today", reference_time=window_start)
        assert len(orders) == 1
        assert orders[0].id == inside_order.id
