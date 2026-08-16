"""
Category Management Service (Task 2.2)
Handles category CRUD operations, activation/deactivation, and lifecycle.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.models import Category
from app.schemas.schemas import CategoryCreate, CategoryUpdate
from app.utils.normalization import derive_key, normalize_display


def _validate_category_name(name: str, db: Session, exclude_id: int | None = None) -> tuple[str, str, str]:
    """
    Shared validation for category creation and renaming.
    Returns (name_raw, name_display, name_key) if valid.
    Raises HTTPException with appropriate error message if invalid.

    Args:
        name: The category name to validate
        db: Database session
        exclude_id: If provided, exclude this category id from duplicate check
                    (used when renaming to allow self-rename like "Drinks" -> "drinks")
    """
    # Validate required and non-empty
    if not name or not name.strip():
        raise HTTPException(400, "Category name is required.")

    # Derive the key and validate it contains alphanumeric
    name_key = derive_key(name)
    if not name_key:
        raise HTTPException(400, "Category name must contain at least one letter or digit.")

    # Check for duplicate name_key
    query = db.query(Category).filter(Category.name_key == name_key)
    if exclude_id is not None:
        query = query.filter(Category.id != exclude_id)

    existing = query.first()
    if existing:
        raise HTTPException(400, f'Category "{existing.name_display}" already exists. Use a different name.')

    # Compute normalized forms
    name_display = normalize_display(name)

    return name, name_display, name_key


def create_category(db: Session, payload: CategoryCreate) -> Category:
    """Create a new category with validation"""
    name_raw, name_display, name_key = _validate_category_name(payload.name, db)

    category = Category(
        name_raw=name_raw,
        name_display=name_display,
        name_key=name_key,
        active=True
    )

    db.add(category)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Could not create category: {str(e)}")

    db.refresh(category)
    return category


def get_category(db: Session, category_id: int) -> Category:
    """Get a category by ID"""
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found.")
    return category


def rename_category(db: Session, category_id: int, payload: CategoryUpdate) -> Category:
    """Rename a category with validation"""
    category = get_category(db, category_id)

    # Validate new name, excluding self from duplicate check
    name_raw, name_display, name_key = _validate_category_name(payload.name, db, exclude_id=category_id)

    # Update all three columns
    category.name_raw = name_raw
    category.name_display = name_display
    category.name_key = name_key

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Could not rename category: {str(e)}")

    db.refresh(category)
    return category


def deactivate_category(db: Session, category_id: int) -> Category:
    """Deactivate a category"""
    category = get_category(db, category_id)

    category.active = False

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Could not deactivate category: {str(e)}")

    db.refresh(category)
    return category


def activate_category(db: Session, category_id: int) -> Category:
    """Activate a category"""
    category = get_category(db, category_id)

    category.active = True

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Could not activate category: {str(e)}")

    db.refresh(category)
    return category
