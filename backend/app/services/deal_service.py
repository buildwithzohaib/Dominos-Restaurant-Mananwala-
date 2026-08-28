"""
Deal Management Service (Phase 11)
Handles deal product CRUD operations and component management.
A deal is a Product with product_type='DEAL' and DealComponent entries.
"""

from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.models import Product, Category, DealComponent, ProductSize
from app.schemas.schemas import DealCreate, DealUpdate, DealComponentCreate, DealComponentOut, DealOut
from app.utils.normalization import derive_key, normalize_display


def _component_to_output(db: Session, component: DealComponent) -> dict:
    """Transform a DealComponent to a dict suitable for DealComponentOut.

    Fetches the component product name and size name for the response.
    """
    # Fetch component product name
    component_product = db.query(Product).filter(
        Product.id == component.component_product_id
    ).first()
    product_name = component_product.name_display if component_product else "Unknown"

    # Fetch size name if applicable
    size_name = None
    if component.size_id:
        size = db.query(ProductSize).filter(ProductSize.id == component.size_id).first()
        size_name = size.name if size else None

    return {
        "id": component.id,
        "product_id": component.component_product_id,  # The component's product ID
        "product_name": product_name,
        "quantity": component.quantity,
        "size_id": component.size_id,
        "size_name": size_name,
    }


def _deal_to_dict(db: Session, deal: Product) -> dict:
    """Transform a deal Product to a dict suitable for DealOut.

    This helper ensures all required fields are present and uses Pydantic
    validation to catch any missing fields automatically.
    """
    deal_dict = {
        "id": deal.id,
        "category_id": deal.category_id,
        "category": {
            "id": deal.category.id,
            "name_display": deal.category.name_display,
            "active": deal.category.active,  # Required by CategoryNested
        },
        "name_display": deal.name_display,
        "price": deal.price,
        "available": deal.available,
        "components": [_component_to_output(db, comp) for comp in deal.components],
        "updated_at": deal.updated_at,
    }

    # Validate against DealOut schema to ensure all fields are present
    return DealOut.model_validate(deal_dict).model_dump(mode="python")


def create_deal(db: Session, payload: DealCreate) -> Product:
    """Create a new deal product with components, all in one transaction.

    A deal is a Product with product_type='DEAL' and a list of DealComponent rows.
    - The deal's price (Product.price) is the total selling price
    - The deal's stock (Product.stock) is always 0 (meaningless for deals)
    - Validation: components must be real products, not deals themselves, with valid sizes
    """

    # Validate that category is provided
    if not payload.category_id:
        raise HTTPException(400, "Category is required.")

    # Validate name
    if not payload.name or not payload.name.strip():
        raise HTTPException(400, "Deal name is required.")

    name_key = derive_key(payload.name)
    if not name_key:
        raise HTTPException(400, "Deal name must contain at least one letter or digit.")

    # Check for duplicate name (by name_key dedup detection)
    existing = db.query(Product).filter(Product.name_key == name_key).first()
    if existing:
        raise HTTPException(400, f'Deal "{existing.name_display}" already exists. Use a different name.')

    # Verify category exists and is active
    category = db.get(Category, payload.category_id)
    if not category:
        raise HTTPException(404, "Category not found.")
    if not category.active:
        raise HTTPException(400, "Cannot add deal to inactive category.")

    # Validate price
    if payload.price <= 0:
        raise HTTPException(400, "Deal price must be positive.")

    # Validate components exist and are valid
    if not payload.components or len(payload.components) == 0:
        raise HTTPException(400, "A deal must have at least one component.")

    component_ids_seen = set()
    for comp in payload.components:
        # Check for duplicate components
        comp_key = (comp.product_id, comp.size_id)
        if comp_key in component_ids_seen:
            raise HTTPException(400, "Duplicate component in deal.")
        component_ids_seen.add(comp_key)

        # Validate quantity
        if comp.quantity < 1:
            raise HTTPException(400, "Component quantity must be at least 1.")

        # Fetch component product
        component_product = db.get(Product, comp.product_id)
        if not component_product:
            raise HTTPException(400, f"Component product {comp.product_id} not found.")

        # Ensure component is not itself a deal
        if component_product.product_type == "DEAL":
            raise HTTPException(400, f'Component "{component_product.name_display}" is a deal. Deals cannot contain other deals.')

        # Validate size if provided
        if comp.size_id is not None:
            size = db.query(ProductSize).filter(
                ProductSize.id == comp.size_id,
                ProductSize.product_id == comp.product_id
            ).first()
            if not size:
                raise HTTPException(400, f'Size {comp.size_id} does not belong to "{component_product.name_display}".')

    # Create deal product (SKU will be set after flush to avoid collisions)
    deal_product = Product(
        category_id=payload.category_id,
        name_raw=payload.name,
        name_display=normalize_display(payload.name),
        name_key=name_key,
        price=payload.price,
        stock=0,  # Deals have no stock; availability determined by components
        sku="DEAL-TEMP",  # Placeholder; will be replaced after flush
        min_stock=0,
        unit="Deal",
        purchase_price=0,
        available=True,
        product_type="DEAL"
    )

    db.add(deal_product)
    db.flush()  # Get the product ID before adding components

    # Set unique SKU based on product ID (guarantees no collisions)
    deal_product.sku = f"DEAL-{deal_product.id}"

    # Add components
    for i, comp in enumerate(payload.components, start=1):
        component = DealComponent(
            product_id=deal_product.id,
            component_product_id=comp.product_id,
            quantity=comp.quantity,
            size_id=comp.size_id,
            sort_order=i
        )
        db.add(component)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Could not create deal: {str(e)}")

    db.refresh(deal_product)

    # Transform components with product/size names
    return _deal_to_dict(db, deal_product)


def get_deal(db: Session, deal_id: int) -> dict:
    """Get a deal by ID with components transformed to include product/size names"""
    deal = db.query(Product).options(
        joinedload(Product.category),
        joinedload(Product.components)
    ).filter(Product.id == deal_id, Product.product_type == "DEAL").first()

    if not deal:
        raise HTTPException(404, "Deal not found.")

    return _deal_to_dict(db, deal)


def list_deals(db: Session, search: str | None = None, include_disabled: bool = False) -> list[dict]:
    """List all deals with optional search. Returns both available and unavailable deals by default.

    Query Parameters:
    - search: Filter by deal name
    - include_disabled: If False (default), only return available deals (matching Products pattern)

    Returns deals with components transformed to include product/size names.
    """
    query = db.query(Product).options(
        joinedload(Product.category),
        joinedload(Product.components)
    ).filter(Product.product_type == "DEAL")

    # Match the Products screen pattern: by default only show available deals
    if not include_disabled:
        query = query.filter(Product.available.is_(True))

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(Product.name_display.ilike(term))

    deals = query.order_by(Product.name_display).all()

    return [_deal_to_dict(db, deal) for deal in deals]


def update_deal(db: Session, deal_id: int, payload: DealUpdate) -> Product:
    """Update a deal's name, category, price, and/or components.

    If components are provided, they replace the entire set: components in the list
    are created/updated, components not in the list are deleted.
    """
    deal = db.query(Product).filter(
        Product.id == deal_id,
        Product.product_type == "DEAL"
    ).first()

    if not deal:
        raise HTTPException(404, "Deal not found.")

    # Update name
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(400, "Deal name cannot be empty.")

        name_key = derive_key(name)
        if not name_key:
            raise HTTPException(400, "Deal name must contain at least one letter or digit.")

        # Check for duplicate name (excluding self)
        existing = db.query(Product).filter(
            Product.name_key == name_key,
            Product.id != deal_id
        ).first()
        if existing:
            raise HTTPException(400, f'Deal "{existing.name_display}" already exists. Use a different name.')

        deal.name_raw = name
        deal.name_display = normalize_display(name)
        deal.name_key = name_key

    # Update category
    if payload.category_id is not None:
        category = db.get(Category, payload.category_id)
        if not category:
            raise HTTPException(404, "Category not found.")
        if not category.active:
            raise HTTPException(400, "Cannot move deal to inactive category.")
        deal.category_id = payload.category_id

    # Update price
    if payload.price is not None:
        if payload.price <= 0:
            raise HTTPException(400, "Deal price must be positive.")
        deal.price = payload.price

    # Update components if provided (None means leave unchanged)
    if payload.components is not None:
        if len(payload.components) == 0:
            raise HTTPException(400, "A deal must have at least one component.")

        # Validate all components
        component_ids_seen = set()
        for comp in payload.components:
            comp_key = (comp.product_id, comp.size_id)
            if comp_key in component_ids_seen:
                raise HTTPException(400, "Duplicate component in deal.")
            component_ids_seen.add(comp_key)

            if comp.quantity < 1:
                raise HTTPException(400, "Component quantity must be at least 1.")

            component_product = db.get(Product, comp.product_id)
            if not component_product:
                raise HTTPException(400, f"Component product {comp.product_id} not found.")

            if component_product.product_type == "DEAL":
                raise HTTPException(400, f'Component "{component_product.name_display}" is a deal. Deals cannot contain other deals.')

            if comp.size_id is not None:
                size = db.query(ProductSize).filter(
                    ProductSize.id == comp.size_id,
                    ProductSize.product_id == comp.product_id
                ).first()
                if not size:
                    raise HTTPException(400, f'Size {comp.size_id} does not belong to "{component_product.name_display}".')

        # Delete existing components and create new ones
        db.query(DealComponent).filter(DealComponent.product_id == deal_id).delete()

        for i, comp in enumerate(payload.components, start=1):
            component = DealComponent(
                product_id=deal_id,
                component_product_id=comp.product_id,
                quantity=comp.quantity,
                size_id=comp.size_id,
                sort_order=i
            )
            db.add(component)

    deal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(deal)

    # Transform components with product/size names
    return _deal_to_dict(db, deal)


def delete_deal(db: Session, deal_id: int) -> None:
    """Delete a deal (soft delete via available=False)"""
    deal = db.query(Product).filter(
        Product.id == deal_id,
        Product.product_type == "DEAL"
    ).first()

    if not deal:
        raise HTTPException(404, "Deal not found.")

    deal.available = False
    deal.updated_at = datetime.utcnow()
    db.commit()
