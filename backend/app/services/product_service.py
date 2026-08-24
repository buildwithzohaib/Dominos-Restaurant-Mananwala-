"""
Product Management Service (Phase 10)
Handles product CRUD operations, enable/disable, and product lifecycle.
"""

from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.models import Product, Category
from app.schemas.schemas import ProductCreate, ProductUpdate
from app.utils.normalization import derive_key, normalize_display
from app.services.sku_service import generate_sku


def create_product(db: Session, payload: ProductCreate) -> Product:
    """Create a new product with validation"""

    # Validate that category is provided
    if not payload.category_id:
        raise HTTPException(400, "Category is required.")

    # Validate required fields
    if not payload.name or not payload.name.strip():
        raise HTTPException(400, "Product name is required.")

    # Validate that name contains at least one alphanumeric character (not just symbols)
    name_key = derive_key(payload.name)
    if not name_key:
        raise HTTPException(400, "Product name must contain at least one letter or digit.")

    # Check for duplicate name (by name_key dedup detection)
    existing = db.query(Product).filter(Product.name_key == name_key).first()
    if existing:
        raise HTTPException(400, f'Product "{existing.name_display}" already exists. Use a different name.')

    # Check for duplicate SKU
    if payload.sku:
        existing = db.query(Product).filter(Product.sku == payload.sku.strip()).first()
        if existing:
            raise HTTPException(400, f'SKU "{payload.sku}" already in use.')

    # Verify category exists
    category = db.get(Category, payload.category_id)
    if not category:
        raise HTTPException(404, "Category not found.")
    if not category.active:
        raise HTTPException(400, "Cannot add product to inactive category.")

    # Validate prices
    if payload.price < 0:
        raise HTTPException(400, "Selling price cannot be negative.")
    if payload.purchase_price is not None and payload.purchase_price < 0:
        raise HTTPException(400, "Purchase price cannot be negative.")

    # Validate stock
    if payload.stock < 0:
        raise HTTPException(400, "Initial stock cannot be negative.")
    if payload.min_stock < 0:
        raise HTTPException(400, "Minimum stock cannot be negative.")

    # Validate unit
    if not payload.unit or not payload.unit.strip():
        raise HTTPException(400, "Unit is required.")

    # Determine SKU: use provided SKU or generate a deterministic one
    if payload.sku:
        sku = payload.sku.strip()
    else:
        sku = generate_sku(db, payload.category_id, category.name_key, name_key)

    # Create product
    product = Product(
        category_id=payload.category_id,
        name_raw=payload.name,
        name_display=normalize_display(payload.name),
        name_key=name_key,
        price=payload.price,
        stock=payload.stock,
        sku=sku,
        min_stock=payload.min_stock,
        unit=payload.unit.strip(),
        purchase_price=payload.purchase_price or 0,
        available=True,
        image=payload.image
    )

    db.add(product)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Could not create product: {str(e)}")

    db.refresh(product)
    return product


def get_product(db: Session, product_id: int, include_disabled: bool = False) -> Product:
    """Get a product by ID"""
    product = db.query(Product).options(joinedload(Product.category)).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Product not found.")
    if not include_disabled and not product.available:
        raise HTTPException(404, "Product not found (disabled).")
    return product


def list_products(db: Session, search: str | None = None, include_disabled: bool = False) -> list[Product]:
    """List products with optional search"""
    query = db.query(Product).options(joinedload(Product.category))

    if not include_disabled:
        query = query.filter(Product.available.is_(True))

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Product.name_display.ilike(term),
                Product.sku.ilike(term)
            )
        )

    return query.order_by(Product.name_display).all()


def update_product(db: Session, product_id: int, payload: ProductUpdate) -> Product:
    """Update product details (name, category, pricing, SKU, unit)"""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found.")

    # Update name (all three columns)
    if payload.name is not None:
        name = payload.name
        if not name or not name.strip():
            raise HTTPException(400, "Product name cannot be empty.")

        # Validate that name contains at least one alphanumeric character
        name_key = derive_key(name)
        if not name_key:
            raise HTTPException(400, "Product name must contain at least one letter or digit.")

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

    # Update category
    if payload.category_id is not None:
        category = db.get(Category, payload.category_id)
        if not category:
            raise HTTPException(404, "Category not found.")
        if not category.active:
            raise HTTPException(400, "Cannot move product to inactive category.")
        product.category_id = payload.category_id

    # Note: SKU is immutable after creation (see ProductUpdate schema) and cannot be changed here

    # Update unit
    if payload.unit is not None:
        unit = payload.unit.strip()
        if not unit:
            raise HTTPException(400, "Unit cannot be empty.")
        product.unit = unit

    # Update purchase price
    if payload.purchase_price is not None:
        if payload.purchase_price < 0:
            raise HTTPException(400, "Purchase price cannot be negative.")
        product.purchase_price = payload.purchase_price

    # Update selling price
    if payload.price is not None:
        if payload.price < 0:
            raise HTTPException(400, "Selling price cannot be negative.")
        product.price = payload.price

    # Update minimum stock
    if payload.min_stock is not None:
        if payload.min_stock < 0:
            raise HTTPException(400, "Minimum stock cannot be negative.")
        product.min_stock = payload.min_stock

    # Update image
    if payload.image is not None:
        product.image = payload.image

    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    return product


def disable_product(db: Session, product_id: int) -> Product:
    """Disable a product (makes it unavailable for sale)"""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found.")

    if not product.available:
        raise HTTPException(400, "Product is already disabled.")

    product.available = False
    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    return product


def enable_product(db: Session, product_id: int) -> Product:
    """Enable a product (makes it available for sale again)"""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found.")

    if product.available:
        raise HTTPException(400, "Product is already enabled.")

    product.available = True
    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    return product
