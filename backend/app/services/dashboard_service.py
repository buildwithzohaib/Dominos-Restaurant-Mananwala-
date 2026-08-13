"""
Dashboard service for calculating business metrics.
Phase 9: Provides real-time overview of restaurant performance.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Order, OrderItem, Product, StockMovement
from app.schemas.schemas import DashboardOverviewOut, HourlySaleItem, TopProductItem


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

    # Define today's date range
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # === SALES CALCULATION ===
    # Sum of totals from PAID orders created today
    sales_result = db.query(func.sum(Order.total)).filter(
        Order.status == "PAID",
        Order.created_at >= today_start,
        Order.created_at < today_end,
    ).scalar()
    sales = Decimal(sales_result or 0).quantize(Decimal("0.01"))

    # === ORDERS COUNT ===
    # Count of PAID orders created today
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
    # Group today's PAID orders by hour and sum their totals
    hourly_sales_data = db.query(
        func.strftime("%H", Order.created_at).label("hour"),
        func.sum(Order.total).label("revenue"),
    ).filter(
        Order.status == "PAID",
        Order.created_at >= today_start,
        Order.created_at < today_end,
    ).group_by(
        func.strftime("%H", Order.created_at)
    ).all()

    # Create hourly breakdown for all 24 hours (even those with no sales = 0)
    hourly_sales_dict = {int(hour): Decimal(revenue or 0).quantize(Decimal("0.01"))
                         for hour, revenue in hourly_sales_data}
    hourly_sales = [
        HourlySaleItem(hour=hour, revenue=hourly_sales_dict.get(hour, Decimal("0")))
        for hour in range(24)
    ]

    # === TOP SELLING PRODUCTS ===
    # Sum quantities of each product sold in PAID orders today
    top_products_data = db.query(
        OrderItem.product_name,
        func.sum(OrderItem.quantity).label("total_quantity"),
        func.sum(OrderItem.line_total).label("total_revenue"),
    ).join(Order).filter(
        Order.status == "PAID",
        Order.created_at >= today_start,
        Order.created_at < today_end,
    ).group_by(OrderItem.product_name).order_by(
        func.sum(OrderItem.quantity).desc()
    ).limit(5).all()

    top_products = [
        TopProductItem(
            product_name=product_name,
            quantity_sold=total_quantity or 0,
            revenue=Decimal(total_revenue or 0).quantize(Decimal("0.01")),
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
