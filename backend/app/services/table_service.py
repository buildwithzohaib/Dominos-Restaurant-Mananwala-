"""
Table Management Service (Phase 11)
Handles table CRUD operations and lifecycle for dine-in orders.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.models import RestaurantTable, Order
from app.schemas.schemas import TableCreate, TableRename


def _normalize_name(name: str) -> str:
    """Normalize table name: strip and collapse multiple spaces."""
    if not name or not name.strip():
        raise HTTPException(400, "Table name is required.")
    return " ".join(name.strip().split())


def _check_duplicate(db: Session, name: str, exclude_id: int | None = None) -> dict | None:
    """
    Check if a table with this name exists (case-insensitive).
    Returns None if no duplicate, or dict with {id, name, is_active} if duplicate found.
    """
    normalized_name = _normalize_name(name)
    query = db.query(RestaurantTable).filter(
        RestaurantTable.name.ilike(normalized_name)
    )
    if exclude_id is not None:
        query = query.filter(RestaurantTable.id != exclude_id)

    existing = query.first()
    if existing:
        return {"id": existing.id, "name": existing.name, "active": existing.active}
    return None


def list_tables(db: Session, include_inactive: bool = False) -> list[RestaurantTable]:
    """List tables with optional inactive filter."""
    query = db.query(RestaurantTable)

    if not include_inactive:
        query = query.filter(RestaurantTable.active.is_(True))

    return query.order_by(RestaurantTable.id).all()


def create_table(db: Session, payload: TableCreate) -> RestaurantTable:
    """Create a new table with validation."""
    normalized_name = _normalize_name(payload.name)

    # Check for duplicate name (case-insensitive)
    duplicate = _check_duplicate(db, payload.name)
    if duplicate:
        if not duplicate["active"]:
            # Duplicate is an inactive table — per Rule 2, the id cannot appear in the
            # message string shown to the user. Return it in structured data instead,
            # so the UI can offer a "Restore this table" button without showing the id.
            raise HTTPException(
                400,
                detail={
                    "message": f'Table "{duplicate["name"]}" already exists but is inactive. Restore it or use a different name.',
                    "inactive_table_id": duplicate["id"]
                }
            )
        else:
            # Duplicate is an active table
            raise HTTPException(400, f'Table "{duplicate["name"]}" already exists.')

    # Create table
    table = RestaurantTable(
        name=normalized_name,
        seats=6,  # Default to 6 seats per Phase 11 spec
        active=True
    )

    db.add(table)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Could not create table: {str(e)}")

    db.refresh(table)
    return table


def rename_table(db: Session, table_id: int, payload: TableRename) -> RestaurantTable:
    """Rename a table with validation."""
    table = db.get(RestaurantTable, table_id)
    if not table:
        raise HTTPException(404, "Table not found.")

    normalized_name = _normalize_name(payload.name)

    # Allow renaming to current name (even different case) — this is intentional:
    # a user can change "Table 1" to "table 1" (normalization only) and it succeeds,
    # or rename "TABLE 1" to "Table 1" to fix capitalization without requiring
    # a different name. This supports incremental corrections.
    if table.name.lower() == normalized_name.lower():
        # Renaming to own name (case-insensitive match): just update to normalized form and return
        table.name = normalized_name
        db.commit()
        db.refresh(table)
        return table

    # Check for duplicate name (case-insensitive, excluding self)
    duplicate = _check_duplicate(db, payload.name, exclude_id=table_id)
    if duplicate:
        if not duplicate["active"]:
            # Duplicate is an inactive table — per Rule 2, the id cannot appear in the
            # message string shown to the user. Return it in structured data instead,
            # so the UI can offer a "Restore this table" button without showing the id.
            raise HTTPException(
                400,
                detail={
                    "message": f'Table "{duplicate["name"]}" already exists but is inactive. Restore it or use a different name.',
                    "inactive_table_id": duplicate["id"]
                }
            )
        else:
            # Duplicate is an active table
            raise HTTPException(400, f'Table "{duplicate["name"]}" already exists.')

    # Update name
    table.name = normalized_name
    db.commit()
    db.refresh(table)
    return table


def deactivate_table(db: Session, table_id: int) -> RestaurantTable:
    """Deactivate a table (soft delete) with validation."""
    table = db.get(RestaurantTable, table_id)
    if not table:
        raise HTTPException(404, "Table not found.")

    if not table.active:
        raise HTTPException(400, "Table is already inactive.")

    # Check for OPEN orders on this table (Rule 8)
    open_order = db.query(Order).filter(
        Order.table_id == table_id,
        Order.status == "OPEN"
    ).first()
    if open_order:
        raise HTTPException(
            400,
            f'Cannot deactivate table "{table.name}" while it has an open order. '
            f'Finish or cancel the order first.'
        )

    # Check if this is the last active table
    active_count = db.query(RestaurantTable).filter(
        RestaurantTable.active.is_(True)
    ).count()
    if active_count == 1:
        raise HTTPException(
            400,
            "Cannot deactivate the last active table. You must have at least one active table."
        )

    # Deactivate the table
    table.active = False
    db.commit()
    db.refresh(table)
    return table


def activate_table(db: Session, table_id: int) -> RestaurantTable:
    """Activate a table (restore soft delete)."""
    table = db.get(RestaurantTable, table_id)
    if not table:
        raise HTTPException(404, "Table not found.")

    if table.active:
        raise HTTPException(400, "Table is already active.")

    # Activate the table
    table.active = True
    db.commit()
    db.refresh(table)
    return table
