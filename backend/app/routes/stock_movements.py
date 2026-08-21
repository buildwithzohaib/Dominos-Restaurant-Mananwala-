from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import StockMovementOut
from app.services import stock_service
from app.routes.auth import get_current_user_dep

# A separate top-level path (rather than nesting under /api/inventory/{product_id})
# so a listing request can never collide with the /api/inventory/{product_id} route.
router = APIRouter(prefix="/api/stock-movements", tags=["stock-movements"], dependencies=[Depends(get_current_user_dep)])


@router.get("", response_model=list[StockMovementOut])
def list_movements(
    search: str | None = Query(default=None),
    movement_type: str | None = Query(default=None),
    date: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return stock_service.list_movements(db, search, movement_type, date)
