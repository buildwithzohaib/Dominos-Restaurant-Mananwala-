from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import InventoryUpdate, ProductOut, StockAdjustmentIn, StockPurchaseIn, StockReconciliationIn, StockMovementOut
from app.services import inventory_service, stock_service
from app.routes.auth import get_current_user_dep

router = APIRouter(prefix="/api/inventory", tags=["inventory"], dependencies=[Depends(get_current_user_dep)])


@router.get("", response_model=list[ProductOut])
def list_inventory(search: str | None = Query(default=None), db: Session = Depends(get_db)):
    return inventory_service.list_inventory(db, search)


@router.get("/{product_id}", response_model=ProductOut)
def get_inventory_item(product_id: int, db: Session = Depends(get_db)):
    return inventory_service.get_inventory_item(db, product_id)


@router.post("/{product_id}/stock", response_model=ProductOut)
def add_stock(product_id: int, payload: StockPurchaseIn, db: Session = Depends(get_db)):
    """Add Stock (Phase 4): a receiving operation — updates Product.stock and writes
    a PURCHASE StockMovement in the same transaction (see stock_service)."""
    return stock_service.add_purchase_stock(db, product_id, payload)


@router.post("/{product_id}/adjust", response_model=ProductOut)
def adjust_stock(product_id: int, payload: StockAdjustmentIn, db: Session = Depends(get_db)):
    """Stock Adjustment (Phase 4): a signed, reasoned correction — updates
    Product.stock and writes an ADJUSTMENT StockMovement in the same transaction."""
    return stock_service.adjust_stock(db, product_id, payload)


@router.put("/{product_id}", response_model=ProductOut)
def update_inventory_item(product_id: int, payload: InventoryUpdate, db: Session = Depends(get_db)):
    return inventory_service.update_inventory_item(db, product_id, payload)


@router.post("/reconcile", response_model=list[StockMovementOut])
def reconcile_stock(payload: StockReconciliationIn, db: Session = Depends(get_db)):
    """Batch stock reconciliation from physical count (Stage 5). For each row where
    counted_quantity differs from system stock, writes one ADJUSTMENT StockMovement.
    Rows where counted == system are skipped. All adjustments happen in one transaction."""
    return stock_service.reconcile_stock(db, payload)
