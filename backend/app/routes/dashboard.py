from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import DashboardOverviewOut, DashboardRangeOut, OrderOut
from app.services import dashboard_service
from app.routes.auth import get_current_user_dep

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user_dep)])


@router.get("/overview", response_model=DashboardOverviewOut)
def get_overview(db: Session = Depends(get_db)):
    """Get today's business overview dashboard metrics.

    Returns:
    - Sales: Total revenue from PAID orders today
    - Orders: Count of PAID orders today
    - Cancelled: Count of orders cancelled today
    - Low Stock: Count of products with low stock
    - Hourly Sales: Revenue breakdown by hour (0-23)
    - Top Products: Top 5 products by quantity sold today
    """
    return dashboard_service.get_dashboard_overview(db)


@router.get("/range", response_model=DashboardRangeOut)
def get_range(
    db: Session = Depends(get_db),
    range: str = "today",
    start: date | None = None,
    end: date | None = None,
):
    """Get range-aware dashboard metrics with profit analysis and staff attribution.

    Query Parameters:
    - range: "today" (default), "7days", "30days", or "custom"
    - start: Required when range="custom". Start date (YYYY-MM-DD format)
    - end: Required when range="custom". End date (YYYY-MM-DD format)

    Returns comprehensive metrics including:
    - Sales and profit figures
    - Payment method and order type breakdown
    - Per-staff attribution (sales and cancellations)
    - Daily and hourly sales trends
    - Top and slowest-selling products
    """
    # Validate range parameter
    valid_ranges = ["today", "7days", "30days", "custom"]
    if range not in valid_ranges:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown range: {range}. Allowed values: {', '.join(valid_ranges)}",
        )

    # Validate custom range parameters
    if range == "custom":
        if start is None or end is None:
            raise HTTPException(
                status_code=400,
                detail="Custom range requires both 'start' and 'end' dates (YYYY-MM-DD format)",
            )
        if start > end:
            raise HTTPException(
                status_code=400,
                detail=f"Start date ({start}) must be before or equal to end date ({end})",
            )

    try:
        return dashboard_service.get_dashboard_range(
            db, range_type=range, custom_start=start, custom_end=end
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/orders", response_model=list[OrderOut])
def get_orders_for_metric(
    db: Session = Depends(get_db),
    metric: str | None = None,
    range: str = "today",
    start: date | None = None,
    end: date | None = None,
    user_id: int | None = None,
    no_user: bool = False,
):
    """Get orders behind a dashboard metric.

    Query Parameters:
    - metric: Required. One of: "sales", "orders", "cancelled", "discounts", "staff"
    - range: "today" (default), "7days", "30days", or "custom"
    - start: Required when range="custom". Start date (YYYY-MM-DD format)
    - end: Required when range="custom". End date (YYYY-MM-DD format)
    - user_id: For "staff" metric, filter by user id
    - no_user: When true for "staff" metric, return "Before staff tracking" orders (where user_id IS NULL)

    Returns:
    - List of Order objects matching the metric, newest first, capped at 200
    """
    # Validate metric parameter
    valid_metrics = ["sales", "orders", "cancelled", "discounts", "staff"]
    if metric is None or metric not in valid_metrics:
        raise HTTPException(
            status_code=400,
            detail=f"metric is required. Allowed values: {', '.join(valid_metrics)}",
        )

    # Validate range parameter
    valid_ranges = ["today", "7days", "30days", "custom"]
    if range not in valid_ranges:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown range: {range}. Allowed values: {', '.join(valid_ranges)}",
        )

    # Validate custom range parameters
    if range == "custom":
        if start is None or end is None:
            raise HTTPException(
                status_code=400,
                detail="Custom range requires both 'start' and 'end' dates (YYYY-MM-DD format)",
            )
        if start > end:
            raise HTTPException(
                status_code=400,
                detail=f"Start date ({start}) must be before or equal to end date ({end})",
            )

    # For "staff" metric, determine the user_id to filter by
    staff_user_id = None
    if metric == "staff":
        if no_user:
            staff_user_id = None  # Explicitly query for IS NULL
        elif user_id is not None:
            staff_user_id = user_id
        # else: user_id not provided and no_user is False - let the service handle it

    try:
        return dashboard_service.get_orders_for_metric(
            db, metric=metric, range_type=range, custom_start=start, custom_end=end,
            user_id=staff_user_id if metric == "staff" else None
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
