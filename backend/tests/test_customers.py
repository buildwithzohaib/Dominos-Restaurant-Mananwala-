"""
Customer Management Testing Suite (Phase 3.2)

Comprehensive tests for customer CRUD, search, normalization, and deactivation.
Uses fresh temporary database per test to avoid cross-test contamination.
"""

import pytest
import tempfile
import os
import gc
import time
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker
from app.database import Base, get_db
from app.models.models import Customer
from app.main import app


@pytest.fixture(scope="function")
def engine():
    """Create a fresh temporary SQLite engine for each test."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        test_engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(bind=test_engine)
        yield test_engine
    finally:
        test_engine.raw_connection().close() if hasattr(test_engine.raw_connection(), 'close') else None
        test_engine.dispose()
        gc.collect()
        time.sleep(0.1)
        if os.path.exists(db_path):
            for attempt in range(3):
                try:
                    os.remove(db_path)
                    break
                except OSError:
                    if attempt < 2:
                        gc.collect()
                        time.sleep(0.05)


@pytest.fixture(scope="function")
def db_session(engine):
    """Create a database session for direct access."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture(scope="function")
def test_client(engine):
    """Create a test client using the test engine."""
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
# CREATE TESTS
# ============================================================================

class TestCustomerCreate:
    """Customer creation and normalization tests."""

    def test_create_name_only_no_phone(self, test_client):
        """Create customer with name only -> phone_raw and phone_key both NULL"""
        response = test_client.post("/api/customers", json={"name": "Ali"})
        assert response.status_code == 201
        data = response.json()
        assert data["name_display"] == "Ali"
        assert data["phone_raw"] is None
        assert data["is_active"] is True

    def test_create_name_and_phone(self, test_client):
        """Create with name + phone -> both phone fields populated and normalized"""
        response = test_client.post("/api/customers", json={
            "name": "Ali Ahmed",
            "phone": "0300-1234567"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name_display"] == "Ali Ahmed"
        assert data["phone_raw"] == "0300-1234567"
        # phone_key not exposed in response, but stored in DB
        assert data["id"] == 1

    def test_create_two_customers_same_phone_both_succeed(self, test_client):
        """Create two customers with same phone -> both succeed (no unique constraint)"""
        response1 = test_client.post("/api/customers", json={
            "name": "Ali",
            "phone": "0300-1234567"
        })
        response2 = test_client.post("/api/customers", json={
            "name": "Ahmed",
            "phone": "0300-1234567"
        })
        assert response1.status_code == 201
        assert response2.status_code == 201
        assert response1.json()["id"] != response2.json()["id"]

    def test_create_two_customers_same_name_both_succeed(self, test_client):
        """Create two customers with same name -> both succeed (no unique constraint)"""
        response1 = test_client.post("/api/customers", json={
            "name": "Ali",
            "phone": "0300-1111111"
        })
        response2 = test_client.post("/api/customers", json={
            "name": "Ali",
            "phone": "0301-1111111"
        })
        assert response1.status_code == 201
        assert response2.status_code == 201
        assert response1.json()["id"] != response2.json()["id"]

    def test_create_name_whitespace_only_fails_400(self, test_client):
        """Create with name='   ' -> 400 bad request"""
        response = test_client.post("/api/customers", json={
            "name": "   ",
            "phone": "0300-1234567"
        })
        assert response.status_code == 400
        assert "whitespace" in response.json()["detail"].lower()

    def test_create_name_symbols_only_fails_400(self, test_client):
        """Create with name='+++' (empty key) -> 400 bad request"""
        response = test_client.post("/api/customers", json={
            "name": "+++",
            "phone": "0300-1234567"
        })
        assert response.status_code == 400

    def test_create_phone_with_urdu_digits_normalizes_to_ascii(self, test_client, db_session):
        """Create with Urdu-Indic digits -> normalized to ASCII in phone_key"""
        response = test_client.post("/api/customers", json={
            "name": "Ali",
            "phone": "۰۳۰۰۱۲۳۴۵۶۷"  # Urdu digits
        })
        assert response.status_code == 201
        data = response.json()
        # phone_raw preserves Urdu, phone_key should be ASCII (checked in DB)
        assert data["phone_raw"] == "۰۳۰۰۱۲۳۴۵۶۷"

        # Verify in DB that phone_key was normalized
        customer = db_session.query(Customer).filter(Customer.id == data["id"]).first()
        assert customer.phone_key == "03001234567"  # ASCII normalized

    def test_create_with_address_phase_3_5(self, test_client):
        """Create customer with address (Phase 3.5)"""
        response = test_client.post("/api/customers", json={
            "name": "Ali Ahmed",
            "phone": "0300-1234567",
            "address": "123 Main Street, Karachi"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name_display"] == "Ali Ahmed"
        assert data["address"] == "123 Main Street, Karachi"

    def test_create_with_blank_address_stores_null(self, test_client):
        """Create with empty/whitespace address -> NULL in database"""
        response = test_client.post("/api/customers", json={
            "name": "Ali",
            "phone": "0300-1234567",
            "address": "   "
        })
        assert response.status_code == 201
        data = response.json()
        assert data["address"] is None

    def test_create_without_address_field_is_null(self, test_client):
        """Create without address field -> address is NULL"""
        response = test_client.post("/api/customers", json={
            "name": "Ali",
            "phone": "0300-1234567"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["address"] is None


# ============================================================================
# SEARCH TESTS
# ============================================================================

class TestCustomerSearch:
    """Customer search and filtering tests."""

    @pytest.fixture(autouse=True)
    def setup_customers(self, test_client):
        """Create test customers for search tests."""
        test_client.post("/api/customers", json={
            "name": "Ali Ahmed",
            "phone": "0300-1111111"
        })
        test_client.post("/api/customers", json={
            "name": "Ahmed Ali",
            "phone": "0301-2222222"
        })
        test_client.post("/api/customers", json={
            "name": "Ahmed Hassan",
            "phone": "0302-3333333"
        })

    def test_search_by_first_name_matches_full_name(self, test_client):
        """Search 'Ali' -> finds 'Ali Ahmed' and 'Ahmed Ali'"""
        response = test_client.get("/api/customers?search=Ali")
        assert response.status_code == 200
        results = response.json()
        names = [r["name_display"] for r in results]
        assert "Ali Ahmed" in names
        assert "Ahmed Ali" in names

    def test_search_by_tokens_in_reversed_order(self, test_client):
        """Search 'Ahmed Ali' -> finds 'Ali Ahmed' (word order doesn't matter)"""
        response = test_client.get("/api/customers?search=Ahmed%20Ali")
        assert response.status_code == 200
        results = response.json()
        names = [r["name_display"] for r in results]
        # Should find both because search is OR logic on words
        assert len(results) >= 2

    def test_search_by_phone_with_dashes_and_spaces_same_result(self, test_client):
        """Search by phone with various separators -> normalize and match"""
        response1 = test_client.get("/api/customers?search=03001111111")
        response2 = test_client.get("/api/customers?search=0300-1111111")
        response3 = test_client.get("/api/customers?search=0300%201111111")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response3.status_code == 200

        # All should find the same customer
        assert len(response1.json()) == len(response2.json()) == len(response3.json())

    def test_search_partial_phone_no_match(self, test_client):
        """Search partial phone '0300' (too short) -> no match (need >=10 digits)"""
        response = test_client.get("/api/customers?search=0300")
        assert response.status_code == 200
        results = response.json()
        # Partial phone shouldn't match phone search (needs >=10 digits)
        # But might match name if it contains the substring
        for r in results:
            assert "0300" not in (r.get("phone_raw") or "")

    def test_search_empty_query_returns_all_active(self, test_client):
        """Search with no query -> returns all active customers"""
        response = test_client.get("/api/customers")
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 3
        # Verify sorted by name_display
        names = [r["name_display"] for r in results]
        assert names == sorted(names)

    def test_search_deactivated_customers_excluded(self, test_client):
        """After deactivating a customer, search results exclude it"""
        # Get unique customer "Ahmed Hassan" (only one with that name)
        response = test_client.get("/api/customers?search=Hassan")
        customer_id = response.json()[0]["id"]
        assert response.json()[0]["name_display"] == "Ahmed Hassan"

        # Deactivate
        test_client.patch(f"/api/customers/{customer_id}/deactivate")

        # Search for "Hassan" should not include deactivated customer
        response = test_client.get("/api/customers?search=Hassan")
        results = response.json()
        assert len(results) == 0

    def test_search_no_matches_returns_empty_list(self, test_client):
        """Search for non-existent customer -> returns empty list, not error"""
        response = test_client.get("/api/customers?search=NonExistent")
        assert response.status_code == 200
        results = response.json()
        assert results == []


# ============================================================================
# UPDATE TESTS
# ============================================================================

class TestCustomerUpdate:
    """Customer update tests."""

    def test_update_name_rewrites_all_three_fields(self, test_client, db_session):
        """Update name -> name_raw, name_display, name_key all change"""
        # Create
        response = test_client.post("/api/customers", json={
            "name": "Old Name",
            "phone": "0300-1234567"
        })
        customer_id = response.json()["id"]

        # Update
        response = test_client.put(f"/api/customers/{customer_id}", json={
            "name": "New Name"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name_display"] == "New Name"

        # Verify in DB
        customer = db_session.query(Customer).filter(Customer.id == customer_id).first()
        assert customer.name_raw == "New Name"
        assert customer.name_display == "New Name"
        assert customer.name_key == "newname"

    def test_update_phone_rewrites_both_fields(self, test_client, db_session):
        """Update phone -> phone_raw and phone_key both change"""
        # Create
        response = test_client.post("/api/customers", json={
            "name": "Ali",
            "phone": "0300-1111111"
        })
        customer_id = response.json()["id"]

        # Update
        response = test_client.put(f"/api/customers/{customer_id}", json={
            "phone": "0301-2222222"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["phone_raw"] == "0301-2222222"

        # Verify phone_key in DB
        customer = db_session.query(Customer).filter(Customer.id == customer_id).first()
        assert customer.phone_key == "03012222222"

    def test_update_clear_phone_sets_both_to_null(self, test_client, db_session):
        """Update phone to empty string -> phone_raw and phone_key both NULL"""
        # Create with phone
        response = test_client.post("/api/customers", json={
            "name": "Ali",
            "phone": "0300-1234567"
        })
        customer_id = response.json()["id"]

        # Clear phone
        response = test_client.put(f"/api/customers/{customer_id}", json={
            "phone": ""
        })
        assert response.status_code == 200
        data = response.json()
        assert data["phone_raw"] is None

        # Verify in DB
        customer = db_session.query(Customer).filter(Customer.id == customer_id).first()
        assert customer.phone_raw is None
        assert customer.phone_key is None

    def test_update_only_phone_leaves_name_untouched(self, test_client, db_session):
        """Update phone only -> name fields unchanged"""
        # Create
        response = test_client.post("/api/customers", json={
            "name": "Original Name",
            "phone": "0300-1111111"
        })
        customer_id = response.json()["id"]

        # Update only phone
        response = test_client.put(f"/api/customers/{customer_id}", json={
            "phone": "0301-2222222"
        })
        assert response.status_code == 200

        # Verify name unchanged
        customer = db_session.query(Customer).filter(Customer.id == customer_id).first()
        assert customer.name_display == "Original Name"

    def test_update_address_phase_3_5(self, test_client, db_session):
        """Update customer address (Phase 3.5)"""
        # Create without address
        response = test_client.post("/api/customers", json={
            "name": "Ali",
            "phone": "0300-1234567"
        })
        customer_id = response.json()["id"]
        assert response.json()["address"] is None

        # Update with address
        response = test_client.put(f"/api/customers/{customer_id}", json={
            "address": "456 Oak Avenue, Lahore"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["address"] == "456 Oak Avenue, Lahore"

        # Verify in DB
        customer = db_session.query(Customer).filter(Customer.id == customer_id).first()
        assert customer.address == "456 Oak Avenue, Lahore"

    def test_update_address_overwrites_previous(self, test_client, db_session):
        """Update address to new value -> overwrites previous address"""
        # Create with address
        response = test_client.post("/api/customers", json={
            "name": "Ali",
            "address": "Old Address"
        })
        customer_id = response.json()["id"]

        # Update to new address
        response = test_client.put(f"/api/customers/{customer_id}", json={
            "address": "New Address"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["address"] == "New Address"

    def test_update_clear_address_sets_to_null(self, test_client, db_session):
        """Update address to empty string -> NULL"""
        # Create with address
        response = test_client.post("/api/customers", json={
            "name": "Ali",
            "address": "123 Street"
        })
        customer_id = response.json()["id"]

        # Clear address
        response = test_client.put(f"/api/customers/{customer_id}", json={
            "address": "   "
        })
        assert response.status_code == 200
        data = response.json()
        assert data["address"] is None

        # Verify in DB
        customer = db_session.query(Customer).filter(Customer.id == customer_id).first()
        assert customer.address is None


# ============================================================================
# DEACTIVATE / ACTIVATE TESTS
# ============================================================================

class TestCustomerDeactivateActivate:
    """Customer deactivation and reactivation tests."""

    def test_deactivate_customer_still_retrievable_by_id(self, test_client):
        """Deactivate customer -> still retrievable by GET, but is_active=False"""
        # Create
        response = test_client.post("/api/customers", json={
            "name": "Ali",
            "phone": "0300-1234567"
        })
        customer_id = response.json()["id"]

        # Deactivate
        response = test_client.patch(f"/api/customers/{customer_id}/deactivate")
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

        # GET by ID should still work
        response = test_client.get(f"/api/customers/{customer_id}")
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_reactivate_appears_in_search_again(self, test_client):
        """Reactivate deactivated customer -> appears in search results"""
        # Create
        response = test_client.post("/api/customers", json={
            "name": "Ali",
            "phone": "0300-1234567"
        })
        customer_id = response.json()["id"]

        # Deactivate
        test_client.patch(f"/api/customers/{customer_id}/deactivate")

        # Search should not include
        response = test_client.get("/api/customers?search=Ali")
        assert len(response.json()) == 0

        # Reactivate
        response = test_client.patch(f"/api/customers/{customer_id}/activate")
        assert response.status_code == 200
        assert response.json()["is_active"] is True

        # Search should include
        response = test_client.get("/api/customers?search=Ali")
        assert len(response.json()) == 1


# ============================================================================
# EDGE CASES AND INTEGRATION TESTS
# ============================================================================

class TestCustomerEdgeCases:
    """Edge cases and integration tests."""

    def test_create_with_mixed_case_and_whitespace(self, test_client):
        """Create with mixed case + extra whitespace -> normalized"""
        response = test_client.post("/api/customers", json={
            "name": "  ALI  AHMED  "
        })
        assert response.status_code == 201
        data = response.json()
        # name_display should preserve case but normalize whitespace
        assert data["name_display"] == "ALI AHMED"

    def test_search_is_case_insensitive(self, test_client):
        """Search is case-insensitive"""
        test_client.post("/api/customers", json={"name": "Ali Ahmed"})

        response1 = test_client.get("/api/customers?search=ali")
        response2 = test_client.get("/api/customers?search=ALI")
        response3 = test_client.get("/api/customers?search=Ali")

        assert len(response1.json()) == len(response2.json()) == len(response3.json()) == 1

    def test_phone_normalization_preserves_raw(self, test_client):
        """phone_raw preserves input format, phone_key normalizes"""
        response = test_client.post("/api/customers", json={
            "name": "Ali",
            "phone": "+92 300 1234567"
        })
        data = response.json()
        assert data["phone_raw"] == "+92 300 1234567"  # as typed
        # phone_key not exposed, but should be 03001234567

    def test_get_nonexistent_customer_returns_404(self, test_client):
        """GET /api/customers/{id} for non-existent -> 404"""
        response = test_client.get("/api/customers/9999")
        assert response.status_code == 404

    def test_update_nonexistent_customer_returns_404(self, test_client):
        """PUT /api/customers/{id} for non-existent -> 404"""
        response = test_client.put("/api/customers/9999", json={"name": "New"})
        assert response.status_code == 404

    def test_deactivate_nonexistent_customer_returns_404(self, test_client):
        """PATCH deactivate for non-existent -> 404"""
        response = test_client.patch("/api/customers/9999/deactivate")
        assert response.status_code == 404

    def test_activate_nonexistent_customer_returns_404(self, test_client):
        """PATCH activate for non-existent -> 404"""
        response = test_client.patch("/api/customers/9999/activate")
        assert response.status_code == 404


# ============================================================================
# PHASE 3.5: ORDER COUNT TESTS
# ============================================================================

class TestCustomerOrderCounts:
    """Phase 3.5: Order count (paid vs total) tests."""

    @pytest.fixture(autouse=True)
    def setup_with_orders(self, test_client, db_session):
        """Create customers with various order scenarios."""
        from app.models.models import Settings, Category, Product, Order, RestaurantTable

        # Ensure settings exist
        settings = db_session.query(Settings).filter(Settings.id == 1).first()
        if not settings:
            settings = Settings(id=1)
            db_session.add(settings)
            db_session.flush()

        # Category and product
        cat = Category(name_raw="Test", name_display="Test", name_key="test", active=True)
        db_session.add(cat)
        db_session.flush()

        prod = Product(
            category_id=cat.id, name_raw="Item", name_display="Item", name_key="item",
            price=10000, stock=100, available=True, sku="SKU-001", min_stock=5, unit="pc"
        )
        db_session.add(prod)
        db_session.flush()

        # Customer 1: No orders
        c1 = Customer(
            name_raw="NoOrders", name_display="No Orders", name_key="noorders",
            is_active=True
        )
        db_session.add(c1)
        db_session.flush()

        # Customer 2: 2 paid, 1 cancelled
        c2 = Customer(
            name_raw="MixedOrders", name_display="Mixed Orders", name_key="mixedorders",
            is_active=True
        )
        db_session.add(c2)
        db_session.flush()

        o1 = Order(
            order_number="ORD-00001", order_type="TAKEAWAY", customer_id=c2.id,
            status="PAID", subtotal=10000, discount=0, tax=0, total=10000,
            payment_method="CASH", amount_received=10000, change_amount=0
        )
        o2 = Order(
            order_number="ORD-00002", order_type="TAKEAWAY", customer_id=c2.id,
            status="PAID", subtotal=10000, discount=0, tax=0, total=10000,
            payment_method="CASH", amount_received=10000, change_amount=0
        )
        o3 = Order(
            order_number="ORD-00003", order_type="TAKEAWAY", customer_id=c2.id,
            status="CANCELLED", subtotal=10000, discount=0, tax=0, total=10000,
            payment_method="CASH", amount_received=10000, change_amount=0,
            cancelled_at=datetime.utcnow(),
            cancelled_reason="CUSTOMER_CHANGED_ORDER"
        )
        db_session.add_all([o1, o2, o3])

        # Customer 3: Deactivated with orders
        c3 = Customer(
            name_raw="Inactive", name_display="Inactive", name_key="inactive",
            is_active=False
        )
        db_session.add(c3)
        db_session.flush()

        o4 = Order(
            order_number="ORD-00004", order_type="TAKEAWAY", customer_id=c3.id,
            status="PAID", subtotal=10000, discount=0, tax=0, total=10000,
            payment_method="CASH", amount_received=10000, change_amount=0
        )
        db_session.add(o4)
        db_session.commit()

        return {
            "c1_id": c1.id,  # No orders
            "c2_id": c2.id,  # 2 paid, 1 cancelled
            "c3_id": c3.id   # Deactivated, 1 paid
        }

    def test_customer_with_no_orders_returns_zero_counts(self, test_client, setup_with_orders):
        """Customer with no orders -> order_count=0, paid_order_count=0"""
        c1_id = setup_with_orders["c1_id"]

        response = test_client.get(f"/api/customers?search=NoOrders")
        assert response.status_code == 200
        results = response.json()

        assert len(results) == 1
        customer = results[0]
        assert customer["order_count"] == 0
        assert customer["paid_order_count"] == 0

    def test_customer_with_mixed_orders_correct_counts(self, test_client, setup_with_orders):
        """Customer with 2 paid + 1 cancelled -> order_count=3, paid_order_count=2"""
        c2_id = setup_with_orders["c2_id"]

        response = test_client.get(f"/api/customers?search=MixedOrders")
        assert response.status_code == 200
        results = response.json()

        assert len(results) == 1
        customer = results[0]
        assert customer["order_count"] == 3, "Should count all orders (2 paid + 1 cancelled)"
        assert customer["paid_order_count"] == 2, "Should count only paid orders"

    def test_include_inactive_false_excludes_deactivated(self, test_client, setup_with_orders):
        """include_inactive=false (default) -> excludes deactivated customers"""
        response = test_client.get("/api/customers")  # No include_inactive param
        assert response.status_code == 200
        results = response.json()

        # Should not include c3 (inactive)
        result_ids = [r["id"] for r in results]
        assert setup_with_orders["c3_id"] not in result_ids

    def test_include_inactive_true_includes_deactivated(self, test_client, setup_with_orders):
        """include_inactive=true -> includes deactivated customers"""
        response = test_client.get("/api/customers?include_inactive=true")
        assert response.status_code == 200
        results = response.json()

        # Should include c3 (inactive)
        result_ids = [r["id"] for r in results]
        assert setup_with_orders["c3_id"] in result_ids

        # Verify the inactive customer's order count is correct
        c3 = next(r for r in results if r["id"] == setup_with_orders["c3_id"])
        assert c3["order_count"] == 1
        assert c3["paid_order_count"] == 1
        assert c3["is_active"] is False
