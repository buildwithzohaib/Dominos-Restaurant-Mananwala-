from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models.models import Order
from app.schemas.schemas import AddItemsIn, OrderCancelIn, OrderCreate, OpenOrderCreate, OrderOut, PayOrderIn, UpdatePendingItemIn
from app.services.order_service import add_items_to_order, cancel_order, create_open_order, create_order, pay_order, send_batch_to_kitchen, update_pending_item

router = APIRouter(prefix="/api/orders", tags=["orders"])

@router.post("", response_model=OrderOut)
def create(payload: OrderCreate, db: Session = Depends(get_db)):
    return create_order(db, payload)

@router.post("/open", response_model=OrderOut)
def open_order(payload: OpenOrderCreate, db: Session = Depends(get_db)):
    return create_open_order(db, payload)

@router.get("", response_model=list[OrderOut])
def list_orders(
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Order).options(joinedload(Order.items), joinedload(Order.table))
    if search and search.strip():
        query = query.filter(Order.order_number.ilike(f"%{search.strip()}%"))
    if status and status.strip():
        query = query.filter(Order.status == status.strip().upper())
    return query.order_by(Order.created_at.desc()).all()

@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).options(joinedload(Order.items), joinedload(Order.table)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found.")
    return order

@router.post("/{order_id}/items", response_model=OrderOut)
def add_items(order_id: int, payload: AddItemsIn, db: Session = Depends(get_db)):
    return add_items_to_order(db, order_id, payload)

@router.patch("/{order_id}/items/{item_id}", response_model=OrderOut)
def update_item(order_id: int, item_id: int, payload: UpdatePendingItemIn, db: Session = Depends(get_db)):
    return update_pending_item(db, order_id, item_id, payload)

@router.post("/{order_id}/send", response_model=OrderOut)
def send_batch(order_id: int, db: Session = Depends(get_db)):
    return send_batch_to_kitchen(db, order_id)

@router.post("/{order_id}/pay", response_model=OrderOut)
def pay(order_id: int, payload: PayOrderIn, db: Session = Depends(get_db)):
    return pay_order(db, order_id, payload)

@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel(order_id: int, payload: OrderCancelIn, db: Session = Depends(get_db)):
    return cancel_order(db, order_id, payload)
