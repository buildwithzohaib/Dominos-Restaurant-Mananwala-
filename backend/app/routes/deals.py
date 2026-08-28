"""
Deal Management API Routes (Phase 11)
Endpoints for creating, reading, updating and deleting deals.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.schemas import DealCreate, DealUpdate, DealOut
from app.services import deal_service
from app.routes.auth import get_current_user_dep

router = APIRouter(prefix="/api/deals", tags=["deals"], dependencies=[Depends(get_current_user_dep)])


@router.get("", response_model=list[DealOut])
def list_deals(
    search: str | None = Query(default=None),
    include_disabled: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """
    List all deals.

    Query Parameters:
    - search: Filter by deal name
    - include_disabled: Include disabled (unavailable) deals in results (default: False)
    """
    return deal_service.list_deals(db, search, include_disabled)


@router.get("/{deal_id}", response_model=DealOut)
def get_deal(
    deal_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific deal by ID"""
    return deal_service.get_deal(db, deal_id)


@router.post("", response_model=DealOut)
def create_deal(
    payload: DealCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new deal.

    Request body:
    - category_id: ID of product category
    - name: Deal name
    - price: Deal price in paisa (e.g., 250000 for Rs. 2500)
    - components: List of components, each with product_id, quantity, and optional size_id
      (e.g., [{"product_id": 5, "quantity": 1, "size_id": 2}, {"product_id": 10, "quantity": 1}])
    """
    return deal_service.create_deal(db, payload)


@router.put("/{deal_id}", response_model=DealOut)
def update_deal(
    deal_id: int,
    payload: DealUpdate,
    db: Session = Depends(get_db),
):
    """
    Update deal details and components.

    If components are provided, they replace the entire set.
    """
    return deal_service.update_deal(db, deal_id, payload)


@router.delete("/{deal_id}")
def delete_deal(
    deal_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a deal (soft delete via available=False).
    """
    deal_service.delete_deal(db, deal_id)
    return {"message": "Deal deleted."}
