"""
Category CRUD Testing Suite
Tests all requirements and edge cases for category management (Phase 2.2).
Includes category lifecycle, name normalization, deduplication, and catalog filtering.
"""

import pytest
import tempfile
import os
import gc
import time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from app.database import Base, get_db
from app.models.models import Category, Product
from app.main import app
from app.utils.normalization import normalize_display, derive_key


@pytest.fixture(scope="function")
def engine():
    """Create a fresh temporary file-based SQLite engine for each test"""
    # Create a temporary file for the database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        # Create engine with the temporary file
        test_engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(bind=test_engine)
        yield test_engine
    finally:
        # Explicitly close all connections before disposal
        test_engine.raw_connection().close() if hasattr(test_engine.raw_connection(), 'close') else None
        test_engine.dispose()

        # Force garbage collection to release file handles
        gc.collect()
        time.sleep(0.1)  # Brief pause to allow OS to release file

        # Clean up the temporary file with retry
        if os.path.exists(db_path):
            for attempt in range(3):
                try:
                    os.remove(db_path)
                    break
                except OSError:
                    if attempt < 2:
                        gc.collect()
                        time.sleep(0.05)
                    # After 3 attempts, file will be cleaned up by OS eventually


@pytest.fixture(scope="function")
def db_session(engine):
    """Create a session using the shared test engine"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture(scope="function")
def test_client(engine):
    """Create a test client using the shared test engine"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


# ============================================================================
# CATEGORY CRUD TESTS
# ============================================================================

def test_create_category_basic(test_client):
    """Test 1: Create a category -> returns name_display, active True"""
    response = test_client.post("/api/categories", json={"name": "Beverages"})
    assert response.status_code == 200
    data = response.json()
    assert data["name_display"] == "Beverages"
    assert data["active"] is True
    assert "id" in data


def test_create_category_with_whitespace(test_client, db_session):
    """Test 2: Create with extra whitespace -> name_display is trimmed and collapsed"""
    response = test_client.post("/api/categories", json={"name": "  Soft   Drinks  "})
    assert response.status_code == 200
    data = response.json()
    cat_id = data["id"]
    # After normalization, multiple spaces collapse and trim
    assert data["name_display"] == "Soft Drinks"

    # Verify internal columns are correct via database
    cat = db_session.query(Category).filter(Category.id == cat_id).first()
    assert cat.name_key == "softdrinks"
    assert cat.name_raw == "  Soft   Drinks  "  # preserves as typed (with leading/trailing whitespace)


def test_create_duplicate_different_case(test_client):
    """Test 3: Create duplicate by different case -> 400, message names EXISTING category"""
    # Create first category
    test_client.post("/api/categories", json={"name": "Drinks"})

    # Try to create duplicate with different case
    response = test_client.post("/api/categories", json={"name": "DRINKS"})
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]
    # Verify it names the existing one
    assert "Drinks" in response.json()["detail"]


def test_create_category_blank_name(test_client):
    """Test 4: Create with '   ' -> 400 'Category name is required.'"""
    response = test_client.post("/api/categories", json={"name": "   "})
    assert response.status_code == 400
    assert "required" in response.json()["detail"].lower()


def test_create_category_symbols_only(test_client):
    """Test 5: Create with '+++' -> 400 'must contain at least one letter or digit'"""
    response = test_client.post("/api/categories", json={"name": "+++"})
    assert response.status_code == 400
    assert "letter or digit" in response.json()["detail"]


def test_rename_category_to_new_name(test_client, db_session):
    """Test 6: Rename to a new name -> all three columns change"""
    # Create category
    post_resp = test_client.post("/api/categories", json={"name": "Drinks"})
    cat_id = post_resp.json()["id"]

    # Rename it
    put_resp = test_client.put(f"/api/categories/{cat_id}", json={"name": "Beverages"})
    assert put_resp.status_code == 200
    data = put_resp.json()

    assert data["name_display"] == "Beverages"

    # Verify all three columns changed in database
    cat = db_session.query(Category).filter(Category.id == cat_id).first()
    assert cat.name_display == "Beverages"
    assert cat.name_key == "beverages"
    assert cat.name_raw == "Beverages"


def test_rename_to_own_name_succeeds(test_client):
    """Test 7: Rename to its own name -> succeeds (self-collision excluded)"""
    # Create category
    post_resp = test_client.post("/api/categories", json={"name": "Drinks"})
    cat_id = post_resp.json()["id"]

    # Rename to same name (should succeed)
    put_resp = test_client.put(f"/api/categories/{cat_id}", json={"name": "Drinks"})
    assert put_resp.status_code == 200
    assert put_resp.json()["name_display"] == "Drinks"


def test_rename_case_change_only(test_client, db_session):
    """Test 8: Rename 'Drinks' to 'DRINKS' -> succeeds, only case changes"""
    # Create category
    post_resp = test_client.post("/api/categories", json={"name": "Drinks"})
    cat_id = post_resp.json()["id"]

    # Rename with case change only
    put_resp = test_client.put(f"/api/categories/{cat_id}", json={"name": "DRINKS"})
    assert put_resp.status_code == 200
    data = put_resp.json()
    assert data["name_display"] == "DRINKS"

    # Verify name_key stays the same (case-insensitive)
    cat = db_session.query(Category).filter(Category.id == cat_id).first()
    assert cat.name_key == "drinks"


def test_rename_onto_another_category_fails(test_client):
    """Test 9: Rename onto another category's key -> 400 naming that other one"""
    # Create two categories
    cat1_resp = test_client.post("/api/categories", json={"name": "Drinks"})
    cat1_id = cat1_resp.json()["id"]

    cat2_resp = test_client.post("/api/categories", json={"name": "Food"})
    cat2_id = cat2_resp.json()["id"]

    # Try to rename cat1 to "Food" (which is cat2's name)
    put_resp = test_client.put(f"/api/categories/{cat1_id}", json={"name": "Food"})
    assert put_resp.status_code == 400
    assert "already exists" in put_resp.json()["detail"]
    # Should name the existing category
    assert "Food" in put_resp.json()["detail"]


def test_get_category_by_id(test_client):
    """Test 10a: GET by id -> 200"""
    # Create category
    post_resp = test_client.post("/api/categories", json={"name": "Drinks"})
    cat_id = post_resp.json()["id"]

    # Get it
    get_resp = test_client.get(f"/api/categories/{cat_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == cat_id


def test_get_category_not_found(test_client):
    """Test 10b: GET id 99999 -> 404"""
    response = test_client.get("/api/categories/99999")
    assert response.status_code == 404


def test_deactivate_category(test_client):
    """Test 11a: Deactivate -> active False"""
    # Create category
    post_resp = test_client.post("/api/categories", json={"name": "Drinks"})
    cat_id = post_resp.json()["id"]
    assert post_resp.json()["active"] is True

    # Deactivate it
    patch_resp = test_client.patch(f"/api/categories/{cat_id}/deactivate")
    assert patch_resp.status_code == 200
    assert patch_resp.json()["active"] is False


def test_activate_category(test_client):
    """Test 11b: Activate -> active True"""
    # Create category
    post_resp = test_client.post("/api/categories", json={"name": "Drinks"})
    cat_id = post_resp.json()["id"]

    # Deactivate it
    test_client.patch(f"/api/categories/{cat_id}/deactivate")

    # Activate it again
    patch_resp = test_client.patch(f"/api/categories/{cat_id}/activate")
    assert patch_resp.status_code == 200
    assert patch_resp.json()["active"] is True


# ============================================================================
# THE JOIN TEST - Category state affects catalog visibility
# ============================================================================

def test_category_deactivation_hides_products_from_catalog(test_client, db_session):
    """
    The bug fix test: deactivating a category hides its products from
    /api/catalog/products, but the product's own `available` flag remains True.
    """
    # Create category
    cat_resp = test_client.post("/api/categories", json={"name": "Drinks"})
    cat_id = cat_resp.json()["id"]

    # Create product in that category
    prod_resp = test_client.post("/api/products", json={
        "name": "Pepsi",
        "category_id": cat_id,
        "price": 8000,
        "stock": 20,
        "sku": "PEPSI-001",
        "unit": "Bottle",
        "min_stock": 5
    })
    assert prod_resp.status_code == 200
    prod_id = prod_resp.json()["id"]

    # Product IS in catalog
    catalog_resp = test_client.get("/api/catalog/products")
    assert catalog_resp.status_code == 200
    product_names = [p["name_display"] for p in catalog_resp.json()]
    assert "Pepsi" in product_names, "Product should be visible in catalog"

    # Deactivate the category
    test_client.patch(f"/api/categories/{cat_id}/deactivate")

    # Product is NOT in catalog anymore
    catalog_resp = test_client.get("/api/catalog/products")
    product_names = [p["name_display"] for p in catalog_resp.json()]
    assert "Pepsi" not in product_names, "Product should be hidden from catalog"

    # But the product row's own `available` is still True in the database
    db_product = db_session.query(Product).filter(Product.id == prod_id).first()
    assert db_product.available is True, "Product.available should still be True"

    # Management view (with include_disabled) still shows it
    mgmt_resp = test_client.get("/api/products?include_disabled=true")
    assert mgmt_resp.status_code == 200
    mgmt_names = [p["name_display"] for p in mgmt_resp.json()]
    assert "Pepsi" in mgmt_names, "Product should be visible in management view"

    # Reactivate the category
    test_client.patch(f"/api/categories/{cat_id}/activate")

    # Product is back in catalog
    catalog_resp = test_client.get("/api/catalog/products")
    product_names = [p["name_display"] for p in catalog_resp.json()]
    assert "Pepsi" in product_names, "Product should be visible again after category reactivation"


# ============================================================================
# ROUTE SEPARATION TESTS
# ============================================================================

def test_catalog_products_ignores_include_disabled(test_client):
    """Test: GET /api/catalog/products ignores include_disabled (has no such param)"""
    # Create a disabled product
    cat_resp = test_client.post("/api/categories", json={"name": "Drinks"})
    cat_id = cat_resp.json()["id"]

    prod_resp = test_client.post("/api/products", json={
        "name": "Pepsi",
        "category_id": cat_id,
        "price": 8000,
        "stock": 20,
        "sku": "PEPSI-001",
        "unit": "Bottle"
    })
    prod_id = prod_resp.json()["id"]

    # Disable it
    test_client.patch(f"/api/products/{prod_id}/disable")

    # catalog endpoint doesn't have include_disabled parameter - disabled products not shown
    catalog_resp = test_client.get("/api/catalog/products?include_disabled=true")
    assert catalog_resp.status_code == 200
    product_names = [p["name_display"] for p in catalog_resp.json()]
    assert "Pepsi" not in product_names, "Disabled product should not appear in catalog"


def test_products_search_filters(test_client):
    """Test: GET /api/products?search=... filters"""
    cat_resp = test_client.post("/api/categories", json={"name": "Drinks"})
    cat_id = cat_resp.json()["id"]

    # Create multiple products
    test_client.post("/api/products", json={
        "name": "Pepsi",
        "category_id": cat_id,
        "price": 8000,
        "stock": 20,
        "sku": "PEPSI-001",
        "unit": "Bottle"
    })

    test_client.post("/api/products", json={
        "name": "Sprite",
        "category_id": cat_id,
        "price": 8000,
        "stock": 15,
        "sku": "SPRITE-001",
        "unit": "Bottle"
    })

    # Search for Pepsi
    search_resp = test_client.get("/api/products?search=Pepsi")
    assert search_resp.status_code == 200
    product_names = [p["name_display"] for p in search_resp.json()]
    assert "Pepsi" in product_names
    assert "Sprite" not in product_names, "Search should filter results"


def test_products_include_disabled_flag(test_client):
    """Test: GET /api/products?include_disabled=true includes disabled product"""
    cat_resp = test_client.post("/api/categories", json={"name": "Drinks"})
    cat_id = cat_resp.json()["id"]

    prod_resp = test_client.post("/api/products", json={
        "name": "Pepsi",
        "category_id": cat_id,
        "price": 8000,
        "stock": 20,
        "sku": "PEPSI-001",
        "unit": "Bottle"
    })
    prod_id = prod_resp.json()["id"]

    # Disable the product
    test_client.patch(f"/api/products/{prod_id}/disable")

    # Without flag: product not shown
    resp_without = test_client.get("/api/products")
    names_without = [p["name_display"] for p in resp_without.json()]
    assert "Pepsi" not in names_without

    # With flag: product is shown
    resp_with = test_client.get("/api/products?include_disabled=true")
    names_with = [p["name_display"] for p in resp_with.json()]
    assert "Pepsi" in names_with, "include_disabled=true should show disabled products"


# ============================================================================
# ORDER VALIDATION — Categories affect sellability
# ============================================================================

def test_order_rejects_product_in_deactivated_category(test_client):
    """Order must reject a product whose category was deactivated"""
    # Create category and product
    cat_resp = test_client.post("/api/categories", json={"name": "Drinks"})
    cat_id = cat_resp.json()["id"]

    prod_resp = test_client.post("/api/products", json={
        "name": "Pepsi",
        "category_id": cat_id,
        "price": 8000,
        "stock": 20,
        "sku": "PEPSI-001",
        "unit": "Bottle"
    })
    prod_id = prod_resp.json()["id"]

    # Deactivate the category
    test_client.patch(f"/api/categories/{cat_id}/deactivate")

    # Order with this product should be rejected
    order_payload = {
        "order_type": "TAKEAWAY",
        "table_id": None,
        "items": [{"product_id": prod_id, "quantity": 1}],
        "discount": 0,
        "tax_rate": 0,
        "payment_method": "CASH",
        "amount_received": 10000
    }
    resp = test_client.post("/api/orders", json=order_payload)
    assert resp.status_code == 400
    assert "disabled category" in resp.json()["detail"]


def test_order_rejects_disabled_product(test_client):
    """Order must reject a disabled product"""
    # Create category and product
    cat_resp = test_client.post("/api/categories", json={"name": "Food"})
    cat_id = cat_resp.json()["id"]

    prod_resp = test_client.post("/api/products", json={
        "name": "Burger",
        "category_id": cat_id,
        "price": 25000,
        "stock": 10,
        "sku": "BURGER-001",
        "unit": "Piece"
    })
    prod_id = prod_resp.json()["id"]

    # Disable the product
    test_client.patch(f"/api/products/{prod_id}/disable")

    # Order with this product should be rejected
    order_payload = {
        "order_type": "TAKEAWAY",
        "table_id": None,
        "items": [{"product_id": prod_id, "quantity": 1}],
        "discount": 0,
        "tax_rate": 0,
        "payment_method": "CASH",
        "amount_received": 30000
    }
    resp = test_client.post("/api/orders", json=order_payload)
    assert resp.status_code == 400
    assert "disabled" in resp.json()["detail"]


def test_order_succeeds_with_active_product_in_active_category(test_client):
    """Order succeeds when product is active and its category is active"""
    # Create category and product
    cat_resp = test_client.post("/api/categories", json={"name": "Snacks"})
    cat_id = cat_resp.json()["id"]

    prod_resp = test_client.post("/api/products", json={
        "name": "Chips",
        "category_id": cat_id,
        "price": 5000,
        "stock": 100,
        "sku": "CHIPS-001",
        "unit": "Packet"
    })
    prod_id = prod_resp.json()["id"]

    # Order should succeed
    order_payload = {
        "order_type": "TAKEAWAY",
        "table_id": None,
        "items": [{"product_id": prod_id, "quantity": 2}],
        "discount": 0,
        "tax_rate": 0,
        "payment_method": "CASH",
        "amount_received": 15000
    }
    resp = test_client.post("/api/orders", json=order_payload)
    assert resp.status_code == 200
    order = resp.json()
    assert order["status"] == "PAID"
    assert len(order["items"]) == 1
    assert order["items"][0]["product_name"] == "Chips"


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
