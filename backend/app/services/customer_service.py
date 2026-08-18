"""
Customer management service.

Follows existing patterns: normalization happens here, database operations
are transactional, business logic is isolated from routes.

Phone can be omitted; if blank, both phone_raw and phone_key are stored as NULL.
"""

from sqlalchemy.orm import Session
from sqlalchemy import or_, func, case
from app.models.models import Customer, Order
from app.utils.normalization import normalize_name
from app.utils.phone import normalize_phone


class EmptyNameKeyError(ValueError):
    """Raised when name normalizes to empty (only whitespace/symbols)."""
    pass


def create(db: Session, name: str, phone: str | None = None, address: str | None = None) -> Customer:
    """
    Create a new customer.

    Args:
        db: database session
        name: customer name (required, will be normalized)
        phone: phone number (optional, will be normalized; NULL if blank)
        address: delivery address (optional, Phase 3.5; NULL if blank)

    Returns:
        The newly created Customer

    Raises:
        EmptyNameKeyError: if name normalizes to empty key
    """
    # Normalize name (same pattern as Product/Category)
    name_raw, name_display, name_key = normalize_name(name)

    if not name_key:
        raise EmptyNameKeyError("Customer name cannot be only whitespace or symbols.")

    # Normalize phone (if provided)
    phone_raw = None
    phone_key = None
    if phone and phone.strip():
        phone_raw = phone.strip()
        phone_key = normalize_phone(phone_raw)
        if not phone_key:  # normalize_phone returns "" if no digits
            phone_raw = None
            phone_key = None

    # Normalize address (Phase 3.5): store as-is if provided, NULL if blank
    address_normalized = address.strip() if address and address.strip() else None

    # Create customer
    customer = Customer(
        name_raw=name_raw,
        name_display=name_display,
        name_key=name_key,
        phone_raw=phone_raw,
        phone_key=phone_key,
        address=address_normalized,
        is_active=True
    )

    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def update(db: Session, customer_id: int, name: str | None = None, phone: str | None = None, address: str | None = None) -> Customer:
    """
    Update customer name, phone, and/or address.

    Args:
        db: database session
        customer_id: customer to update
        name: new name (optional; if provided, normalized)
        phone: new phone (optional; NULL if blank)
        address: new address (optional, Phase 3.5; NULL if blank)

    Returns:
        Updated Customer

    Raises:
        EmptyNameKeyError: if name normalizes to empty
        ValueError: if customer not found
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise ValueError(f"Customer {customer_id} not found")

    # Update name if provided
    if name is not None:
        name_raw, name_display, name_key = normalize_name(name)
        if not name_key:
            raise EmptyNameKeyError("Customer name cannot be only whitespace or symbols.")
        customer.name_raw = name_raw
        customer.name_display = name_display
        customer.name_key = name_key

    # Update phone if provided
    if phone is not None:
        if phone.strip():
            phone_raw = phone.strip()
            phone_key = normalize_phone(phone_raw)
            if phone_key:  # Only update if normalization succeeds
                customer.phone_raw = phone_raw
                customer.phone_key = phone_key
            else:
                # No valid digits in phone; clear it
                customer.phone_raw = None
                customer.phone_key = None
        else:
            # Empty phone; clear both fields
            customer.phone_raw = None
            customer.phone_key = None

    # Update address if provided (Phase 3.5)
    if address is not None:
        customer.address = address.strip() if address.strip() else None

    db.commit()
    db.refresh(customer)
    return customer


def get(db: Session, customer_id: int) -> Customer | None:
    """Fetch customer by ID."""
    return db.query(Customer).filter(Customer.id == customer_id).first()


def deactivate(db: Session, customer_id: int) -> Customer:
    """Soft-delete customer (set is_active=False)."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise ValueError(f"Customer {customer_id} not found")

    customer.is_active = False
    db.commit()
    db.refresh(customer)
    return customer


def activate(db: Session, customer_id: int) -> Customer:
    """Restore customer (set is_active=True)."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise ValueError(f"Customer {customer_id} not found")

    customer.is_active = True
    db.commit()
    db.refresh(customer)
    return customer


def search(db: Session, query: str = "", include_inactive: bool = False) -> list[dict]:
    """
    Search customers by name or phone, with order counts (Phase 3.5).

    If query is empty, returns all active customers sorted by name_display.

    If query has digits, also searches by phone_key (normalized).
    Always searches by name (substring match on name_key, word-based).

    Args:
        db: database session
        query: search term (name or phone)
        include_inactive: if True, include deactivated customers

    Returns:
        List of dicts: {id, name_display, phone_raw, address, is_active,
                        order_count, paid_order_count}
    """
    # Base query with order counts (Phase 3.5)
    base_query = db.query(
        Customer.id,
        Customer.name_display,
        Customer.phone_raw,
        Customer.address,
        Customer.is_active,
        func.count(Order.id).label('order_count'),
        func.coalesce(
            func.sum(case((Order.status == "PAID", 1), else_=0)),
            0
        ).label('paid_order_count')
    ).outerjoin(Order, Order.customer_id == Customer.id)

    # Apply active/inactive filter
    if not include_inactive:
        base_query = base_query.filter(Customer.is_active == True)

    if not query or not query.strip():
        # Empty query: return all matching, sorted by name
        results = base_query.group_by(Customer.id).order_by(Customer.name_display).all()
        return [dict(r._mapping) for r in results]

    query = query.strip()
    results = []
    is_active_filter = Customer.is_active if not include_inactive else True

    # Try phone search (if query looks like phone)
    phone_key = normalize_phone(query)
    if phone_key:  # non-empty string
        phone_results = base_query.filter(
            Customer.phone_key == phone_key
        ).group_by(Customer.id).all()
        results.extend(phone_results)

    # Always try name search (substring match on name_key)
    words = query.lower().split()
    filters = [Customer.name_key.contains(word) for word in words]
    if filters:
        name_results = base_query.filter(
            or_(*filters)
        ).group_by(Customer.id).all()
        results.extend(name_results)

    # Deduplicate by id (phone search might also match name)
    seen = set()
    unique = []
    for row in results:
        row_dict = dict(row._mapping)
        if row_dict['id'] not in seen:
            seen.add(row_dict['id'])
            unique.append(row_dict)

    return unique
