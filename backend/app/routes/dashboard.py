from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.schemas import DashboardOverviewOut
from app.services import dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


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
