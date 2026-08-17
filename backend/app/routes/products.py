"""
Product Management API Routes (Phase 10)
Endpoints for creating, reading, updating, and managing products.
"""

from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Product
from app.schemas.schemas import ProductCreate, ProductOut, ProductUpdate
from app.services import product_service, image_service

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(
    search: str | None = Query(default=None),
    include_disabled: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """
    List all products.

    Query Parameters:
    - search: Filter by product name or SKU
    - include_disabled: Include disabled products in results
    """
    return product_service.list_products(db, search, include_disabled)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific product by ID"""
    return product_service.get_product(db, product_id, include_disabled=False)


@router.post("", response_model=ProductOut)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new product.

    Request body:
    - category_id: ID of product category
    - name: Product name
    - price: Selling price (must be > 0)
    - purchase_price: Cost price (optional)
    - stock: Initial stock quantity
    - min_stock: Minimum stock threshold
    - sku: Stock keeping unit (optional, auto-generated if not provided)
    - unit: Unit of measurement (Piece, Bottle, Portion, etc.)
    - image: Product image URL (optional)
    """
    return product_service.create_product(db, payload)


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
):
    """
    Update product details.

    Note: This endpoint does NOT update stock quantity.
    Use /api/inventory endpoints for stock operations.
    """
    return product_service.update_product(db, product_id, payload)


@router.patch("/{product_id}/disable", response_model=ProductOut)
def disable_product(
    product_id: int,
    db: Session = Depends(get_db),
):
    """
    Disable a product (remove from POS without deleting).

    Disabled products:
    - Do not appear in POS product list
    - Cannot be added to new orders
    - Remain in historical orders
    - Can be re-enabled at any time
    """
    return product_service.disable_product(db, product_id)


@router.patch("/{product_id}/enable", response_model=ProductOut)
def enable_product(
    product_id: int,
    db: Session = Depends(get_db),
):
    """
    Enable a previously disabled product.

    Re-enables the product for sale in POS based on current stock status.
    """
    return product_service.enable_product(db, product_id)


@router.post("/{product_id}/image", response_model=ProductOut)
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload or replace a product image.

    Accepts JPEG and PNG images up to 10 MB. Images are center-cropped and
    resized to exactly 400x300 pixels (no letterboxing). Returns the updated product.

    Raises 400 if:
    - File exceeds 10 MB
    - File is not a valid image
    - Image format is not JPEG or PNG
    """
    # Check product exists
    product = db.get(Product, product_id)
    if not product:
        from fastapi import HTTPException
        raise HTTPException(404, "Product not found.")

    # Process image
    filename, image_hash = await image_service.process_product_image(file, product_id)

    # Update product
    product.image = filename
    product.image_hash = image_hash
    db.commit()
    db.refresh(product)

    return product


@router.delete("/{product_id}/image", response_model=ProductOut)
def delete_product_image(
    product_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a product's image and clear image metadata.

    Deletes the image file from disk and clears the image and image_hash columns.
    This is not a soft delete — the file is permanently removed. Uploaded files are
    ephemeral artifacts (unlike database records) with no historical audit value.

    Returns 200 whether the image existed or not (idempotent operation).
    If the database says there is an image but the file is missing, the columns
    are still cleared and no error is raised.

    Raises 404 if the product does not exist.
    """
    import os
    from fastapi import HTTPException

    # Check product exists
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found.")

    # If product has an image, delete the file
    if product.image:
        filepath = os.path.join(image_service.STORAGE_DIR, product.image)
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            # If file is already missing or can't be deleted, continue anyway
            # Clear the database columns regardless
            pass

    # Clear image metadata
    product.image = None
    product.image_hash = None
    db.commit()
    db.refresh(product)

    return product
