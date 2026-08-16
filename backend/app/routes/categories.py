"""
Category Management API Routes (Task 2.2)
Endpoints for creating, reading, updating, and managing categories.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.models.models import Category

from app.database import get_db
from app.schemas.schemas import CategoryCreate, CategoryUpdate, CategoryOut
from app.services import category_service

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    """
    Get all categories (active and inactive).

    Used by management UIs and dropdowns. Returns both active and inactive
    categories so that products in inactive categories can still be edited.
    """
    return db.query(Category).order_by(Category.name_display).all()


@router.post("", response_model=CategoryOut)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new category.

    Request body:
    - name: Category name

    Returns the created category with id, name_display, and active status.
    """
    return category_service.create_category(db, payload)


@router.get("/{category_id}", response_model=CategoryOut)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific category by ID"""
    return category_service.get_category(db, category_id)


@router.put("/{category_id}", response_model=CategoryOut)
def rename_category(
    category_id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
):
    """
    Rename a category.

    Request body:
    - name: New category name

    All three text columns (name_raw, name_display, name_key) are updated.
    """
    return category_service.rename_category(db, category_id, payload)


@router.patch("/{category_id}/deactivate", response_model=CategoryOut)
def deactivate_category(
    category_id: int,
    db: Session = Depends(get_db),
):
    """
    Deactivate a category.

    Products in this category will no longer appear in the POS grid.
    The products themselves remain unchanged; reactivating the category
    restores them instantly.
    """
    return category_service.deactivate_category(db, category_id)


@router.patch("/{category_id}/activate", response_model=CategoryOut)
def activate_category(
    category_id: int,
    db: Session = Depends(get_db),
):
    """
    Activate a category.

    Products in this category will reappear in the POS grid in their
    previous state (available/disabled flags unchanged).
    """
    return category_service.activate_category(db, category_id)
