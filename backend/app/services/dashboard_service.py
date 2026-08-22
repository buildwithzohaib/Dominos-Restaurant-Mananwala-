"""
Dashboard service for calculating business metrics.
Phase 9: Provides real-time overview of restaurant performance.
Stage 8: Range-aware metrics with profit calculation and per-staff attribution.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Order, OrderItem, Product, StockMovement, User
from app.schemas.schemas import (
    DashboardOverviewOut, HourlySaleItem, TopProductItem,
    DashboardRangeOut, DailySalesItem, StaffMetricsItem
)
from app.utils.dates import get_business_day_boundaries


def get_dashboard_overview(db: Session) -> DashboardOverviewOut:
    """
    Calculates today's business metrics:
    - Total sales from PAID orders (excluding CANCELLED)
    - Count of today's orders (PAID)
    - Count of today's cancelled orders
    - Count of low-stock products
    - Hourly sales breakdown
    - Top 5 selling products by quantity
    """

    # Define business day range (respects settings.day_starts_at, not UTC midnight)
    today_start, today_end = get_business_day_boundaries(db, datetime.now(timezone.utc))

    # === SALES CALCULATION ===
    # Sum of totals from PAID orders paid today (in paisa).
    # Uses paid_at, not created_at, because revenue exists only when payment is received.
    sales_result = db.query(func.sum(Order.total)).filter(
        Order.status == "PAID",
        Order.paid_at >= today_start,
        Order.paid_at < today_end,
    ).scalar()
    sales = sales_result or 0

    # === ORDERS COUNT ===
    # Count of PAID orders created today.
    # OPEN QUESTION: should this be created_at or paid_at? "orders placed today" vs "orders paid today".
    # For now, uses created_at (order placement time) — a defensible, simple reading.
    orders_count = db.query(func.count(Order.id)).filter(
        Order.status == "PAID",
        Order.created_at >= today_start,
        Order.created_at < today_end,
    ).scalar() or 0

    # === CANCELLED COUNT ===
    # Count of orders cancelled today (using cancelled_at timestamp)
    cancelled_count = db.query(func.count(Order.id)).filter(
        Order.status == "CANCELLED",
        Order.cancelled_at >= today_start,
        Order.cancelled_at < today_end,
    ).scalar() or 0

    # === LOW STOCK COUNT ===
    # Count of products with LOW_STOCK or OUT_OF_STOCK status
    # A product is LOW_STOCK if: 0 < stock <= min_stock
    # A product is OUT_OF_STOCK if: stock <= 0
    low_stock_count = db.query(func.count(Product.id)).filter(
        Product.available.is_(True),  # Only count active products
        Product.stock <= Product.min_stock,  # stock <= min_stock (includes 0)
    ).scalar() or 0

    # === HOURLY SALES BREAKDOWN ===
    # Group today's PAID orders by hour (of payment) and sum their totals.
    # Uses paid_at to bucket revenue by the hour it was received, not when the order was created.
    hourly_sales_data = db.query(
        func.strftime("%H", Order.paid_at).label("hour"),
        func.sum(Order.total).label("revenue"),
    ).filter(
        Order.status == "PAID",
        Order.paid_at >= today_start,
        Order.paid_at < today_end,
    ).group_by(
        func.strftime("%H", Order.paid_at)
    ).all()

    # Create hourly breakdown for all 24 hours (even those with no sales = 0), in paisa
    hourly_sales_dict = {int(hour): revenue or 0
                         for hour, revenue in hourly_sales_data}
    hourly_sales = [
        HourlySaleItem(hour=hour, revenue=hourly_sales_dict.get(hour, 0))
        for hour in range(24)
    ]

    # === TOP SELLING PRODUCTS ===
    # Sum quantities of each product sold in PAID orders today (by payment time).
    # Uses paid_at to reflect products actually sold (paid for) today, not ordered.
    top_products_data = db.query(
        OrderItem.product_name,
        func.sum(OrderItem.quantity).label("total_quantity"),
        func.sum(OrderItem.line_total).label("total_revenue"),
    ).join(Order).filter(
        Order.status == "PAID",
        Order.paid_at >= today_start,
        Order.paid_at < today_end,
    ).group_by(OrderItem.product_name).order_by(
        func.sum(OrderItem.quantity).desc()
    ).limit(5).all()

    top_products = [
        TopProductItem(
            product_name=product_name,
            quantity_sold=total_quantity or 0,
            revenue=total_revenue or 0,  # in paisa
        )
        for product_name, total_quantity, total_revenue in top_products_data
    ]

    return DashboardOverviewOut(
        sales=sales,
        orders=orders_count,
        cancelled=cancelled_count,
        low_stock=low_stock_count,
        hourly_sales=hourly_sales,
        top_products=top_products,
    )


# ============================================================================
# STAGE 8: RANGE-AWARE DASHBOARD METRICS
# ============================================================================

def resolve_range(db: Session, range_type: str, custom_start: datetime | None = None,
                 custom_end: datetime | None = None, reference_time: datetime | None = None) -> tuple[tuple[datetime, datetime], tuple[datetime, datetime]]:
    """
    Resolve a range request into (current_window, previous_window) tuples of (start, end) datetimes.

    Args:
        db: SQLAlchemy session for fetching settings
        range_type: "today", "7days", "30days", or "custom"
        custom_start: Start date (date object or datetime, converted to business day start) for "custom" range
        custom_end: End date (date object or datetime, converted to business day end) for "custom" range
        reference_time: Current time (defaults to now). Used for relative ranges like "7days".

    Returns:
        Tuple of (current_window, previous_window) where each window is (start, end) datetimes.
        Both windows are business-day aware (respect settings.day_starts_at).
    """
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    # Strip timezone for consistency with rest of codebase
    if reference_time.tzinfo is not None:
        reference_time = reference_time.replace(tzinfo=None)

    if range_type == "today":
        # Current window: today's business day
        current_start, current_end = get_business_day_boundaries(db, reference_time)
        # Previous window: yesterday's business day
        yesterday = reference_time - timedelta(days=1)
        prev_start, prev_end = get_business_day_boundaries(db, yesterday)

    elif range_type == "7days":
        # Current window: last 7 business days (ending with today)
        # End: today's business day end
        _, current_end = get_business_day_boundaries(db, reference_time)
        # Start: business day start of (today - 6 days) — includes today, so 7 days total
        six_days_ago = reference_time - timedelta(days=6)
        current_start, _ = get_business_day_boundaries(db, six_days_ago)

        # Previous window: 7 days before current window (same length)
        prev_end = current_start  # Previous ends where current started
        thirteen_days_ago = reference_time - timedelta(days=13)
        prev_start, _ = get_business_day_boundaries(db, thirteen_days_ago)

    elif range_type == "30days":
        # Current window: last 30 business days (ending with today)
        # End: today's business day end
        _, current_end = get_business_day_boundaries(db, reference_time)
        # Start: business day start of (today - 29 days) — includes today, so 30 days total
        twenty_nine_days_ago = reference_time - timedelta(days=29)
        current_start, _ = get_business_day_boundaries(db, twenty_nine_days_ago)

        # Previous window: 30 days before current window (same length)
        prev_end = current_start  # Previous ends where current started
        fifty_nine_days_ago = reference_time - timedelta(days=59)
        prev_start, _ = get_business_day_boundaries(db, fifty_nine_days_ago)

    elif range_type == "custom":
        if custom_start is None or custom_end is None:
            raise ValueError("custom range requires custom_start and custom_end")

        # Convert date objects to datetime if needed
        # Anchor dates at midday (12:00) to ensure they fall within their own business day
        if hasattr(custom_start, 'year') and not hasattr(custom_start, 'hour'):
            # It's a date object, convert to datetime at midday
            custom_start = datetime.combine(custom_start, datetime(1, 1, 1, 12, 0, 0).time())
        if hasattr(custom_end, 'year') and not hasattr(custom_end, 'hour'):
            # It's a date object, convert to datetime at midday
            custom_end = datetime.combine(custom_end, datetime(1, 1, 1, 12, 0, 0).time())

        # Get business day boundaries for the provided dates
        # custom_start at midday -> business day START of that date
        # custom_end at midday -> business day END of that date
        current_start, _ = get_business_day_boundaries(db, custom_start)
        _, current_end = get_business_day_boundaries(db, custom_end)

        # Previous window: same length, ending where current started
        window_length = (current_end - current_start).days
        prev_end = current_start
        prev_start = prev_end - timedelta(days=window_length)
        # Adjust to business day boundary
        prev_start, _ = get_business_day_boundaries(db, prev_start)
    else:
        raise ValueError(f"Unknown range type: {range_type}")

    return (current_start, current_end), (prev_start, prev_end)


def get_dashboard_range(db: Session, range_type: str = "today",
                       custom_start: datetime | None = None,
                       custom_end: datetime | None = None,
                       reference_time: datetime | None = None) -> DashboardRangeOut:
    """
    Calculate range-aware dashboard metrics with profit analysis and per-staff attribution.

    All metrics filter on PAID orders by paid_at timestamp, except cancellations which use cancelled_at.
    Profit is computed per-order, excluding orders with any NULL or <=0 item costs.

    Args:
        db: SQLAlchemy session
        range_type: "today", "7days", "30days", or "custom"
        custom_start: Start date for custom range
        custom_end: End date for custom range
        reference_time: Current time (defaults to now). Used for deterministic testing.
    """
    current_window, prev_window = resolve_range(db, range_type, custom_start, custom_end, reference_time)
    current_start, current_end = current_window
    prev_start, prev_end = prev_window

    # === CURRENT WINDOW METRICS ===

    # Sales: sum of Order.total for PAID orders
    current_sales = db.query(func.sum(Order.total)).filter(
        Order.status == "PAID",
        Order.paid_at >= current_start,
        Order.paid_at < current_end,
    ).scalar() or 0

    # Orders count: PAID orders in window
    current_orders = db.query(func.count(Order.id)).filter(
        Order.status == "PAID",
        Order.paid_at >= current_start,
        Order.paid_at < current_end,
    ).scalar() or 0

    # Profit calculation: per-order logic with cost validation
    current_profit, current_orders_missing_cost = _calculate_profit(
        db, current_start, current_end
    )

    # Calculate profit margin
    if current_profit > 0 and current_sales > 0:
        # Revenue = subtotal - discount (what customer paid for goods/services, before tax/delivery)
        current_revenue = db.query(func.sum(Order.subtotal - Order.discount)).filter(
            Order.status == "PAID",
            Order.paid_at >= current_start,
            Order.paid_at < current_end,
        ).scalar() or 0
        current_profit_margin_pct = int((current_profit * 10000) / current_revenue) if current_revenue > 0 else 0
    else:
        current_profit_margin_pct = 0

    # Average order value
    current_avg_order_value = int(current_sales / current_orders) if current_orders > 0 else 0

    # Payment method breakdown
    payment_breakdown = db.query(
        Order.payment_method,
        func.count(Order.id).label("count"),
        func.sum(Order.total).label("total_sales"),
    ).filter(
        Order.status == "PAID",
        Order.paid_at >= current_start,
        Order.paid_at < current_end,
    ).group_by(Order.payment_method).all()

    current_cash_orders = 0
    current_card_orders = 0
    current_other_orders = 0
    current_cash_sales = 0
    current_card_sales = 0

    for method, count, total_sales in payment_breakdown:
        if method == "CASH":
            current_cash_orders = count
            current_cash_sales = total_sales or 0
        elif method == "CARD":
            current_card_orders = count
            current_card_sales = total_sales or 0
        elif method == "OTHER":
            current_other_orders = count

    # Discount metrics
    discount_data = db.query(
        func.count(Order.id).label("discount_orders"),
        func.sum(Order.discount).label("total_discount"),
    ).filter(
        Order.status == "PAID",
        Order.discount > 0,
        Order.paid_at >= current_start,
        Order.paid_at < current_end,
    ).all()

    current_discount_total = 0
    current_discount_order_count = 0
    if discount_data and discount_data[0][0]:
        current_discount_order_count = discount_data[0][0]
        current_discount_total = discount_data[0][1] or 0

    # Cancellations
    cancelled_data = db.query(
        func.count(Order.id).label("cancel_count"),
        func.sum(Order.total).label("cancel_value"),
    ).filter(
        Order.status == "CANCELLED",
        Order.cancelled_at >= current_start,
        Order.cancelled_at < current_end,
    ).all()

    current_cancelled_count = 0
    current_cancelled_value = 0
    if cancelled_data and cancelled_data[0][0]:
        current_cancelled_count = cancelled_data[0][0]
        current_cancelled_value = cancelled_data[0][1] or 0

    # Order type breakdown
    order_type_data = db.query(
        Order.order_type,
        func.count(Order.id).label("count"),
    ).filter(
        Order.status == "PAID",
        Order.paid_at >= current_start,
        Order.paid_at < current_end,
    ).group_by(Order.order_type).all()

    current_dine_in_count = 0
    current_takeaway_count = 0
    current_delivery_count = 0

    for order_type, count in order_type_data:
        if order_type == "DINE_IN":
            current_dine_in_count = count
        elif order_type == "TAKEAWAY":
            current_takeaway_count = count
        elif order_type == "DELIVERY":
            current_delivery_count = count

    # Low stock count
    low_stock_count = db.query(func.count(Product.id)).filter(
        Product.available.is_(True),
        Product.stock <= Product.min_stock,
    ).scalar() or 0

    # Daily sales (one row per business day in window)
    daily_sales = _calculate_daily_sales(db, current_start, current_end)

    # Hourly sales
    hourly_sales = _calculate_hourly_sales(db, current_start, current_end)

    # Top products (top 8)
    top_products = _calculate_top_products(db, current_start, current_end, limit=8)

    # Slow products (bottom 5 that sold at least once)
    slow_products = _calculate_slow_products(db, current_start, current_end, limit=5)

    # Per-staff metrics
    per_staff = _calculate_per_staff_metrics(db, current_start, current_end)

    # === PREVIOUS WINDOW METRICS ===
    prev_sales = db.query(func.sum(Order.total)).filter(
        Order.status == "PAID",
        Order.paid_at >= prev_start,
        Order.paid_at < prev_end,
    ).scalar() or 0

    return DashboardRangeOut(
        range_type=range_type,
        window_start=current_start,
        window_end=current_end,
        sales=current_sales,
        sales_previous=prev_sales,
        profit=current_profit,
        profit_margin_pct=current_profit_margin_pct,
        orders_missing_cost=current_orders_missing_cost,
        orders=current_orders,
        average_order_value=current_avg_order_value,
        cash_orders=current_cash_orders,
        card_orders=current_card_orders,
        other_orders=current_other_orders,
        cash_sales=current_cash_sales,
        card_sales=current_card_sales,
        discount_total=current_discount_total,
        discount_order_count=current_discount_order_count,
        cancelled_count=current_cancelled_count,
        cancelled_value=current_cancelled_value,
        dine_in_count=current_dine_in_count,
        takeaway_count=current_takeaway_count,
        delivery_count=current_delivery_count,
        low_stock_count=low_stock_count,
        daily_sales=daily_sales,
        hourly_sales=hourly_sales,
        top_products=top_products,
        slow_products=slow_products,
        per_staff=per_staff,
    )


def _calculate_profit(db: Session, window_start: datetime, window_end: datetime) -> tuple[int, int]:
    """
    Calculate total profit and count of orders excluded due to missing/zero cost.

    Profit per order = (subtotal - discount) - sum(item.cost * item.quantity)
    Orders excluded: any with cost NULL or cost <= 0 on ANY item.
    """
    # Get all PAID orders in window with their items
    orders = db.query(Order).filter(
        Order.status == "PAID",
        Order.paid_at >= window_start,
        Order.paid_at < window_end,
    ).all()

    total_profit = 0
    orders_missing_cost = 0

    for order in orders:
        # Check if any item has NULL or <=0 cost
        has_missing_cost = any(
            item.cost is None or item.cost <= 0
            for item in order.items
        )

        if has_missing_cost:
            orders_missing_cost += 1
            continue

        # Calculate cost for this order
        order_cost = sum(
            (item.cost or 0) * item.quantity
            for item in order.items
        )

        # Revenue = subtotal - discount (excludes tax and delivery_charge)
        order_revenue = order.subtotal - order.discount

        # Profit = revenue - cost
        order_profit = order_revenue - order_cost
        total_profit += order_profit

    return total_profit, orders_missing_cost


def _calculate_daily_sales(db: Session, window_start: datetime, window_end: datetime) -> list[DailySalesItem]:
    """Generate daily sales grouped by business day (matching all other metrics).

    Each business day runs from window_start + N days to window_start + (N+1) days.
    A payment at any time within that window belongs to that business day.
    """
    result = []
    current_day_start = window_start

    while current_day_start < window_end:
        current_day_end = current_day_start + timedelta(days=1)

        # Sum all orders paid within this business day
        day_revenue = db.query(func.sum(Order.total)).filter(
            Order.status == "PAID",
            Order.paid_at >= current_day_start,
            Order.paid_at < current_day_end,
        ).scalar() or 0

        # Use the calendar date at the start of this business day
        business_day_date = current_day_start.date()
        result.append(DailySalesItem(
            date=business_day_date,
            revenue=day_revenue,
        ))

        current_day_start = current_day_end

    return result


def _calculate_hourly_sales(db: Session, window_start: datetime, window_end: datetime) -> list[HourlySaleItem]:
    """Calculate hourly sales across entire window."""
    hourly_data = db.query(
        func.strftime("%H", Order.paid_at).label("hour"),
        func.sum(Order.total).label("revenue"),
    ).filter(
        Order.status == "PAID",
        Order.paid_at >= window_start,
        Order.paid_at < window_end,
    ).group_by(func.strftime("%H", Order.paid_at)).all()

    hourly_dict = {int(hour): revenue or 0 for hour, revenue in hourly_data}

    return [
        HourlySaleItem(hour=hour, revenue=hourly_dict.get(hour, 0))
        for hour in range(24)
    ]


def _calculate_top_products(db: Session, window_start: datetime, window_end: datetime, limit: int = 8) -> list[TopProductItem]:
    """Get top-selling products by quantity."""
    top_data = db.query(
        OrderItem.product_name,
        func.sum(OrderItem.quantity).label("total_quantity"),
        func.sum(OrderItem.line_total).label("total_revenue"),
    ).join(Order).filter(
        Order.status == "PAID",
        Order.paid_at >= window_start,
        Order.paid_at < window_end,
    ).group_by(OrderItem.product_name).order_by(
        func.sum(OrderItem.quantity).desc()
    ).limit(limit).all()

    return [
        TopProductItem(
            product_name=product_name,
            quantity_sold=total_quantity or 0,
            revenue=total_revenue or 0,
        )
        for product_name, total_quantity, total_revenue in top_data
    ]


def _calculate_slow_products(db: Session, window_start: datetime, window_end: datetime, limit: int = 5) -> list[TopProductItem]:
    """Get slowest-selling products (that sold at least once)."""
    slow_data = db.query(
        OrderItem.product_name,
        func.sum(OrderItem.quantity).label("total_quantity"),
        func.sum(OrderItem.line_total).label("total_revenue"),
    ).join(Order).filter(
        Order.status == "PAID",
        Order.paid_at >= window_start,
        Order.paid_at < window_end,
    ).group_by(OrderItem.product_name).order_by(
        func.sum(OrderItem.quantity).asc()
    ).limit(limit).all()

    return [
        TopProductItem(
            product_name=product_name,
            quantity_sold=total_quantity or 0,
            revenue=total_revenue or 0,
        )
        for product_name, total_quantity, total_revenue in slow_data
    ]


def _calculate_per_staff_metrics(db: Session, window_start: datetime, window_end: datetime) -> list[StaffMetricsItem]:
    """Calculate per-staff sales, order counts, and cancellations."""
    # Sales and orders attributed to users
    sales_data = db.query(
        Order.performed_by_user_id,
        func.sum(Order.total).label("sales"),
        func.count(Order.id).label("order_count"),
        func.sum(Order.discount).label("discount_total"),
    ).filter(
        Order.status == "PAID",
        Order.paid_at >= window_start,
        Order.paid_at < window_end,
    ).group_by(Order.performed_by_user_id).all()

    # Cancellations attributed to users
    cancel_data = db.query(
        Order.cancel_order_performed_by_user_id,
        func.count(Order.id).label("cancel_count"),
    ).filter(
        Order.status == "CANCELLED",
        Order.cancelled_at >= window_start,
        Order.cancelled_at < window_end,
    ).group_by(Order.cancel_order_performed_by_user_id).all()

    cancel_dict = {user_id: count for user_id, count in cancel_data}

    # Fetch all users mentioned in sales or cancellations (single query for efficiency)
    user_ids = set(u[0] for u in sales_data) | set(u[0] for u in cancel_data)
    user_ids.discard(None)  # Remove None entry

    users_by_id = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        users_by_id = {u.id: u.name for u in users}

    # Build result with user names
    result = []
    sales_user_ids = set(u[0] for u in sales_data)

    for user_id, sales, order_count, discount_total in sales_data:
        user_name = users_by_id.get(user_id) if user_id is not None else None

        result.append(StaffMetricsItem(
            user_id=user_id,
            user_name=user_name,
            sales=sales or 0,
            orders=order_count or 0,
            cancelled=cancel_dict.get(user_id, 0),
            discount_total=discount_total or 0,
        ))

    # Add users who only have cancellations
    for user_id, cancel_count in cancel_data:
        if user_id not in sales_user_ids:
            user_name = users_by_id.get(user_id) if user_id is not None else None

            result.append(StaffMetricsItem(
                user_id=user_id,
                user_name=user_name,
                sales=0,
                orders=0,
                cancelled=cancel_count,
                discount_total=0,
            ))

    return result
