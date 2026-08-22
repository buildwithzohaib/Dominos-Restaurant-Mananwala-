from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import DashboardOverviewOut, DashboardRangeOut
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
