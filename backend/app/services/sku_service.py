"""
SKU Generation Service (Task 2.5)

Pure function build_sku() generates deterministic, collision-free SKUs.
Wrapper generate_sku() queries the database and delegates to build_sku.
"""


def build_sku(
    category_name_key: str,
    product_name_key: str,
    category_id: int,
    taken: set[str]
) -> str:
    """
    Generate a deterministic, collision-free SKU.

    Pure function: no database access. Returns the first available SKU
    not in the `taken` set.

    SKU format: {CAT_PREFIX}-{PROD_ABBR}-{SEQ:03d}
    - CAT_PREFIX: first 3 ASCII alphanumeric chars of category_name_key (uppercase),
      or C{category_id:02d} if name_key has no ASCII
    - PROD_ABBR: first 3 ASCII alphanumeric chars of product_name_key (uppercase),
      or GEN if name_key has no ASCII
    - SEQ: 001, incremented to 002, 003, etc. on collision

    Args:
        category_name_key: lowercase alphanumeric from derive_key(category.name)
        product_name_key: lowercase alphanumeric from derive_key(product.name)
        category_id: numeric category ID (used as fallback)
        taken: set of SKUs already in the database

    Returns:
        A unique SKU not in `taken`
    """
    # Derive category prefix
    cat_prefix = _derive_prefix(category_name_key, f"C{category_id:02d}")

    # Derive product abbreviation
    prod_abbr = _derive_prefix(product_name_key, "GEN")

    # Find next available sequence number
    seq = 1
    while True:
        candidate = f"{cat_prefix}-{prod_abbr}-{seq:03d}"
        if candidate not in taken:
            return candidate
        seq += 1


def _derive_prefix(name_key: str, fallback: str) -> str:
    """
    Derive a 2-4 character prefix from name_key.

    Takes the first up to 3 ASCII alphanumeric characters and uppercases them.
    If name_key is empty or contains no ASCII letters, returns fallback.

    Examples:
        "fastfood" -> "FAS"
        "drinks" -> "DRI"
        "7up" -> "7UP"
        "a" -> "A" (fewer than 3 chars is OK)
        "" (or non-ASCII) -> fallback (e.g. "GEN" or "C05")

    Args:
        name_key: lowercase alphanumeric string (output of derive_key)
        fallback: string to return if name_key has no ASCII alphanumeric

    Returns:
        A 1-4 character prefix, uppercase
    """
    if not name_key:
        return fallback

    # Extract ASCII alphanumeric characters (letters and digits)
    ascii_chars = "".join(c for c in name_key if c.isascii() and c.isalnum())

    if not ascii_chars:
        return fallback

    # Take up to first 3 characters, uppercase
    return ascii_chars[:3].upper()


def generate_sku(
    db,
    category_id: int,
    category_name_key: str,
    product_name_key: str
) -> str:
    """
    Generate a unique SKU by querying existing SKUs and calling build_sku.

    Wrapper around build_sku that handles database queries.

    Args:
        db: SQLAlchemy Session
        category_id: numeric category ID
        category_name_key: category.name_key
        product_name_key: product.name_key

    Returns:
        A unique SKU
    """
    from app.models.models import Product

    # Get all existing SKUs
    existing_skus = {row[0] for row in db.query(Product.sku).all()}

    return build_sku(category_name_key, product_name_key, category_id, existing_skus)
