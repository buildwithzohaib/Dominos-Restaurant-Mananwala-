from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models.models import Order
from app.schemas.schemas import OrderCancelIn, OrderCreate, OrderOut
from app.services.order_service import cancel_order, create_order

router = APIRouter(prefix="/api/orders", tags=["orders"])

@router.post("", response_model=OrderOut)
def create(payload: OrderCreate, db: Session = Depends(get_db)):
    return create_order(db, payload)

@router.get("", response_model=list[OrderOut])
def list_orders(
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Order).options(joinedload(Order.items))
    if search and search.strip():
        query = query.filter(Order.order_number.ilike(f"%{search.strip()}%"))
    if status and status.strip():
        query = query.filter(Order.status == status.strip().upper())
    return query.order_by(Order.created_at.desc()).all()

@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found.")
    return order

@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel(order_id: int, payload: OrderCancelIn, db: Session = Depends(get_db)):
    return cancel_order(db, order_id, payload)
