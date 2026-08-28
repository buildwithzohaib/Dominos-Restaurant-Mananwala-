from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models.models import Category, Product, RestaurantTable, User
from app.schemas.schemas import CategoryOut, ProductOut, TableOut, TableCreate, TableRename
from app.services import table_service, deal_service
from app.routes.auth import get_current_user_dep

router = APIRouter(prefix="/api", tags=["catalog"], dependencies=[Depends(get_current_user_dep)])

@router.get("/catalog/categories", response_model=list[CategoryOut])
def catalog_categories(db: Session = Depends(get_db)):
    """Get all active categories for the POS catalog/grid."""
    return db.query(Category).filter(Category.active.is_(True)).order_by(Category.name_display).all()

@router.get("/catalog/products", response_model=list[ProductOut])
def catalog_products(db: Session = Depends(get_db)):
    # Return both regular products and deals for the POS grid (Phase 11)
    # Deals and products both filter by available and active category.
    # Regular products return unchanged; deals have components transformed to include product/size names.
    products = db.query(Product)\
        .options(joinedload(Product.category), joinedload(Product.sizes), joinedload(Product.components))\
        .join(Category, Product.category_id == Category.id)\
        .filter(Product.available.is_(True), Category.active.is_(True))\
        .order_by(Product.name_display)\
        .all()

    # For deals, transform components to include product_name and size_name
    # (reuse the logic from deal_service to avoid duplication)
    result = []
    for product in products:
        product_dict = {
            "id": product.id,
            "category_id": product.category_id,
            "category": product.category,
            "name_display": product.name_display,
            "price": product.price,
            "stock": product.stock,
            "image": product.image,
            "image_hash": product.image_hash,
            "available": product.available,
            "status": product.status,
            "sku": product.sku,
            "min_stock": product.min_stock,
            "unit": product.unit,
            "purchase_price": product.purchase_price,
            "stock_status": product.stock_status,
            "product_type": product.product_type,
            "sizes": product.sizes,
            "updated_at": product.updated_at,
        }

        # For deals, build components with product_name and size_name
        if product.product_type == "DEAL":
            # Transform each component to include product_name and size_name (Phase 11)
            components = [deal_service._component_to_output(db, comp) for comp in product.components]
            product_dict["components"] = components
        else:
            product_dict["components"] = []

        result.append(product_dict)

    return result

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
