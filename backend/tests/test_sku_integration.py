"""
Integration test for SKU generation (Task 2.5)

Tests that generate_sku works end-to-end when creating products.
Creates its own fresh database for each test — no dependency on pos.db.
"""

import pytest
import tempfile
import os
import gc
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import Product, Category, Base
from app.schemas.schemas import ProductCreate
from app.services.product_service import create_product


@pytest.fixture(scope="function")
def fresh_test_db():
    """
    Create a fresh temporary SQLite database and seed it with categories and seed products.

    This fixture:
    1. Creates a temporary in-memory database
    2. Builds all tables from SQLAlchemy models
    3. Seeds with 4 categories and 4 seed products
    4. Yields a session for the test
    5. Cleans up after the test

    Seed data (matching pos.db):
    - Categories: Fast Food, Deals, Drinks, Snacks
    - Products: FF-NUG-001, FF-FRY-001, DEAL-ZFD-001, DRK-PEP-001
    """
    # Create temporary database
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()

    # Seed categories
    categories = [
        Category(id=1, name_raw="Fast Food", name_display="Fast Food", name_key="fastfood", active=True),
        Category(id=2, name_raw="Deals", name_display="Deals", name_key="deals", active=True),
        Category(id=3, name_raw="Drinks", name_display="Drinks", name_key="drinks", active=True),
        Category(id=4, name_raw="Snacks", name_display="Snacks", name_key="snacks", active=True),
    ]
    session.add_all(categories)

    # Seed products (4 seed SKUs)
    products = [
        Product(
            id=1,
            category_id=1,
            name_raw="Chicken Nuggets",
            name_display="Chicken Nuggets",
            name_key="chickennuggets",
            price=20000,
            stock=100,
            sku="FF-NUG-001",
            min_stock=5,
            unit="pc",
            purchase_price=10000,
            available=True,
        ),
        Product(
            id=2,
            category_id=1,
            name_raw="Regular Fries",
            name_display="Regular Fries",
            name_key="regularfries",
            price=15000,
            stock=50,
            sku="FF-FRY-001",
            min_stock=5,
            unit="portion",
            purchase_price=8000,
            available=True,
        ),
        Product(
            id=3,
            category_id=2,
            name_raw="Zinger + Fries + Drink",
            name_display="Zinger + Fries + Drink",
            name_key="zingerfriesdrink",
            price=35000,
            stock=30,
            sku="DEAL-ZFD-001",
            min_stock=2,
            unit="set",
            purchase_price=18000,
            available=True,
        ),
        Product(
            id=4,
            category_id=3,
            name_raw="Pepsi",
            name_display="Pepsi",
            name_key="pepsi",
            price=8000,
            stock=200,
            sku="DRK-PEP-001",
            min_stock=10,
            unit="bottle",
            purchase_price=4000,
            available=True,
        ),
    ]
    session.add_all(products)
    session.commit()

    yield session

    session.close()


def test_sku_generation_chicken_roll(fresh_test_db):
    """
    Create "Chicken Roll" in Fast Food with no SKU.

    Expected derivation:
    - Category: "Fast Food" → name_key="fastfood" → "FAS"
    - Product: "Chicken Roll" → name_key="chickenroll" → "CHI"
    - Taken SKUs: FF-NUG-001, FF-FRY-001, DEAL-ZFD-001, DRK-PEP-001
    - "FAS-CHI-001" is new → expect FAS-CHI-001
    """
    payload = ProductCreate(
        category_id=1,  # Fast Food
        name="Chicken Roll",
        price=25000,
        purchase_price=12000,
        stock=10,
        min_stock=2,
        unit="pc",
        sku=None,
    )

    product = create_product(fresh_test_db, payload)
    sku = product.sku

    print(f"Product 1 (Chicken Roll): SKU = {sku}")
    assert sku == "FAS-CHI-001", f"Expected FAS-CHI-001, got {sku}"


def test_sku_generation_collision(fresh_test_db):
    """
    Create "Chilli Cheese Fries" in Fast Food — collision with Chicken Roll.

    Expected: FAS-CHI-002 (collision handling)
    """
    # First, create Chicken Roll
    payload1 = ProductCreate(
        category_id=1,
        name="Chicken Roll",
        price=25000,
        purchase_price=12000,
        stock=10,
        min_stock=2,
        unit="pc",
        sku=None,
    )
    product1 = create_product(fresh_test_db, payload1)

    # Then create Chilli Cheese Fries (collision on CHI prefix)
    payload2 = ProductCreate(
        category_id=1,
        name="Chilli Cheese Fries",
        price=22000,
        purchase_price=10000,
        stock=15,
        min_stock=3,
        unit="portion",
        sku=None,
    )
    product2 = create_product(fresh_test_db, payload2)
    sku = product2.sku

    print(f"Product 2 (Chilli Cheese Fries): SKU = {sku}")
    assert sku == "FAS-CHI-002", f"Expected FAS-CHI-002, got {sku}"


def test_sku_generation_urdu_name(fresh_test_db):
    """
    Create product with Urdu name "چکن رول" in Fast Food.

    Expected: FAS-GEN-001 (non-ASCII fallback)
    """
    payload = ProductCreate(
        category_id=1,
        name="چکن رول",  # Urdu: Chicken Roll
        price=30000,
        purchase_price=15000,
        stock=8,
        min_stock=1,
        unit="pc",
        sku=None,
    )

    product = create_product(fresh_test_db, payload)
    sku = product.sku

    print(f"Product (Urdu Chicken Roll): SKU = {sku}")
    assert sku == "FAS-GEN-001", f"Expected FAS-GEN-001, got {sku}"


def test_explicit_sku_still_works(fresh_test_db):
    """
    Provide an explicit SKU — should be used as-is, not regenerated.
    """
    payload = ProductCreate(
        category_id=2,  # Deals
        name="Custom SKU Product",
        price=15000,
        purchase_price=8000,
        stock=5,
        min_stock=1,
        unit="item",
        sku="CUSTOM-PROD-001",
    )

    product = create_product(fresh_test_db, payload)
    sku = product.sku

    print(f"Explicit SKU product: SKU = {sku}")
    assert sku == "CUSTOM-PROD-001", f"Expected CUSTOM-PROD-001, got {sku}"


def test_seed_skus_untouched(fresh_test_db):
    """
    Verify that the seed SKUs are never modified.
    """
    seed_products = fresh_test_db.query(Product).filter(Product.id <= 4).all()

    expected_skus = {
        1: "FF-NUG-001",
        2: "FF-FRY-001",
        3: "DEAL-ZFD-001",
        4: "DRK-PEP-001",
    }

    print("\n=== Seed Products (untouched) ===")
    for product in seed_products:
        expected = expected_skus.get(product.id)
        status = "✓" if product.sku == expected else "✗"
        print(f"{status} ID {product.id}: {product.name_display} -> {product.sku}")
        assert product.sku == expected, f"Seed SKU mismatch for ID {product.id}"
