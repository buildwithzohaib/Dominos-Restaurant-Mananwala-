from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.models import Product
from app.schemas.schemas import InventoryUpdate
from app.utils.normalization import derive_key, normalize_display


def list_inventory(db: Session, search: str | None = None) -> list[Product]:
    query = db.query(Product)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Product.name_display.ilike(term), Product.sku.ilike(term)))
    return query.order_by(Product.name_display).all()


def get_inventory_item(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found.")
    return product


def update_inventory_item(db: Session, product_id: int, payload: InventoryUpdate) -> Product:
    """Edit flow: item name, SKU, minimum stock, unit, purchase price, selling price.
    Current stock is intentionally excluded — see add_stock()."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found.")

    if payload.name is not None:
        name = payload.name
        if not name or not name.strip():
            raise HTTPException(400, "Item name cannot be empty.")

        # Validate that name contains at least one alphanumeric character
        name_key = derive_key(name)
        if not name_key:
            raise HTTPException(400, "Item name must contain at least one letter or digit.")

        # Check for duplicate name (excluding self)
        existing = db.query(Product).filter(
            Product.name_key == name_key,
            Product.id != product_id
        ).first()
        if existing:
            raise HTTPException(400, f'Product "{existing.name_display}" already exists. Use a different name.')

        product.name_raw = name
        product.name_display = normalize_display(name)
        product.name_key = name_key

    if payload.sku is not None:
        sku = payload.sku.strip()
        if not sku:
            raise HTTPException(400, "SKU cannot be empty.")
        conflict = (
            db.query(Product)
            .filter(Product.sku == sku, Product.id != product_id)
            .first()
        )
        if conflict:
            raise HTTPException(400, f'SKU "{sku}" is already used by another product.')
        product.sku = sku

    if payload.unit is not None:
        unit = payload.unit.strip()
        if not unit:
            raise HTTPException(400, "Unit cannot be empty.")
        product.unit = unit

    if payload.min_stock is not None:
        if payload.min_stock < 0:
            raise HTTPException(400, "Minimum stock cannot be negative.")
        product.min_stock = payload.min_stock

    if payload.purchase_price is not None:
        if payload.purchase_price < 0:
            raise HTTPException(400, "Purchase price cannot be negative.")
        product.purchase_price = payload.purchase_price

    if payload.price is not None:
        if payload.price < 0:
            raise HTTPException(400, "Selling price cannot be negative.")
        product.price = payload.price  # POS, cart and receipt all read this same field

    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    return product
