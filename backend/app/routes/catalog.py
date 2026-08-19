from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Category, Product, RestaurantTable
from app.schemas.schemas import CategoryOut, ProductOut, TableOut, TableCreate, TableRename
from app.services import table_service

router = APIRouter(prefix="/api", tags=["catalog"])

@router.get("/catalog/categories", response_model=list[CategoryOut])
def catalog_categories(db: Session = Depends(get_db)):
    """Get all active categories for the POS catalog/grid."""
    return db.query(Category).filter(Category.active.is_(True)).order_by(Category.name_display).all()

@router.get("/catalog/products", response_model=list[ProductOut])
def catalog_products(db: Session = Depends(get_db)):
    return db.query(Product)\
        .join(Category, Product.category_id == Category.id)\
        .filter(Product.available.is_(True), Category.active.is_(True))\
        .order_by(Product.name_display)\
        .all()

@router.get("/tables", response_model=list[TableOut])
def list_tables(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db)
):
    """List tables with optional inactive filter."""
    return table_service.list_tables(db, include_inactive)

@router.post("/tables", response_model=TableOut)
def create_table(
    payload: TableCreate,
    db: Session = Depends(get_db)
):
    """Create a new table."""
    return table_service.create_table(db, payload)

@router.put("/tables/{table_id}", response_model=TableOut)
def rename_table(
    table_id: int,
    payload: TableRename,
    db: Session = Depends(get_db)
):
    """Rename a table."""
    return table_service.rename_table(db, table_id, payload)

@router.patch("/tables/{table_id}/deactivate", response_model=TableOut)
def deactivate_table(
    table_id: int,
    db: Session = Depends(get_db)
):
    """Deactivate a table (soft delete)."""
    return table_service.deactivate_table(db, table_id)

@router.patch("/tables/{table_id}/activate", response_model=TableOut)
def activate_table(
    table_id: int,
    db: Session = Depends(get_db)
):
    """Activate a table (restore from soft delete)."""
    return table_service.activate_table(db, table_id)
