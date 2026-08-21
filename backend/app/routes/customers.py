"""
Customer management API routes.

Endpoints:
  POST   /api/customers              - Create customer
  GET    /api/customers?search=...   - Search/list customers (empty search = all active)
  GET    /api/customers/{id}         - Get customer by ID
  PUT    /api/customers/{id}         - Update customer
  PATCH  /api/customers/{id}/deactivate - Soft-delete
  PATCH  /api/customers/{id}/activate   - Restore
"""

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import get_db
from app.models.models import User
from app.schemas.schemas import CustomerCreate, CustomerUpdate, CustomerOut, CustomerSearchResult
from app.services import customer_service
from app.routes.auth import get_current_user_dep

router = APIRouter(prefix="/api/customers", tags=["customers"], dependencies=[Depends(get_current_user_dep)])


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    """Create a new customer."""
    try:
        customer = customer_service.create(
            db=db,
            name=payload.name,
            phone=payload.phone,
            address=payload.address
        )
        return customer
    except (ValueError, customer_service.EmptyNameKeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[CustomerSearchResult])
def search_customers(
    search: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db)
):
    """
    Search customers by name or phone (Phase 3.5: with order counts).

    If 'search' parameter is omitted or empty, returns all matching customers
    ordered by name_display.

    If 'search' contains digits, also matches by normalized phone number.
    Always searches by name (substring match on name_key).

    By default, returns only active customers. Set include_inactive=true to
    include deactivated customers in results.
    """
    query = search if search else ""
    results = customer_service.search(db=db, query=query, include_inactive=include_inactive)
    return results


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    """Get customer by ID."""
    customer = customer_service.get(db=db, customer_id=customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return customer


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: Session = Depends(get_db)
):
    """Update customer name, phone, and/or address."""
    try:
        customer = customer_service.update(
            db=db,
            customer_id=customer_id,
            name=payload.name,
            phone=payload.phone,
            address=payload.address
        )
        return customer
    except ValueError as e:
        # ValueError from normalize_name or customer not found
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except customer_service.EmptyNameKeyError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{customer_id}/deactivate", response_model=CustomerOut)
def deactivate_customer(customer_id: int, db: Session = Depends(get_db)):
    """Soft-delete customer (set is_active=False)."""
    try:
        customer = customer_service.deactivate(db=db, customer_id=customer_id)
        return customer
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{customer_id}/activate", response_model=CustomerOut)
def activate_customer(customer_id: int, db: Session = Depends(get_db)):
    """Restore customer (set is_active=True)."""
    try:
        customer = customer_service.activate(db=db, customer_id=customer_id)
        return customer
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
