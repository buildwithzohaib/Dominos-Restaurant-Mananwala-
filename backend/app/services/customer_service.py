"""
Customer management service.

Follows existing patterns: normalization happens here, database operations
are transactional, business logic is isolated from routes.

Phone can be omitted; if blank, both phone_raw and phone_key are stored as NULL.
"""

from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.models import Customer
from app.utils.normalization import normalize_name
from app.utils.phone import normalize_phone


class EmptyNameKeyError(ValueError):
    """Raised when name normalizes to empty (only whitespace/symbols)."""
    pass


def create(db: Session, name: str, phone: str | None = None) -> Customer:
    """
    Create a new customer.

    Args:
        db: database session
        name: customer name (required, will be normalized)
        phone: phone number (optional, will be normalized; NULL if blank)

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

    # Create customer
    customer = Customer(
        name_raw=name_raw,
        name_display=name_display,
        name_key=name_key,
        phone_raw=phone_raw,
        phone_key=phone_key,
        is_active=True
    )

    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def update(db: Session, customer_id: int, name: str | None = None, phone: str | None = None) -> Customer:
    """
    Update customer name and/or phone.

    Args:
        db: database session
        customer_id: customer to update
        name: new name (optional; if provided, normalized)
        phone: new phone (optional; NULL if blank)

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


def search(db: Session, query: str = "", include_inactive: bool = False) -> list[Customer]:
    """
    Search customers by name or phone.

    If query is empty, returns all active customers sorted by name_display.

    If query has digits, also searches by phone_key (normalized).
    Always searches by name (substring match on name_key, word-based).

    Args:
        db: database session
        query: search term (name or phone)
        include_inactive: if True, include deactivated customers

    Returns:
        List of matching customers
    """
    if not query or not query.strip():
        # Empty query: return all active, sorted by name
        return db.query(Customer).filter(
            Customer.is_active == (not include_inactive) if not include_inactive else True
        ).order_by(Customer.name_display).all()

    query = query.strip()
    results = []
    is_active_filter = Customer.is_active if not include_inactive else True

    # Try phone search (if query looks like phone)
    phone_key = normalize_phone(query)
    if phone_key:  # non-empty string
        phone_results = db.query(Customer).filter(
            Customer.phone_key == phone_key,
            is_active_filter
        ).all()
        results.extend(phone_results)

    # Always try name search (substring match on name_key)
    # Split query into words and search for all words (OR logic)
    words = query.lower().split()
    filters = [Customer.name_key.contains(word) for word in words]
    if filters:
        name_results = db.query(Customer).filter(
            or_(*filters),
            is_active_filter
        ).all()
        results.extend(name_results)

    # Deduplicate by id (phone search might also match name)
    seen = set()
    unique = []
    for customer in results:
        if customer.id not in seen:
            seen.add(customer.id)
            unique.append(customer)

    return unique
