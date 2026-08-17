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
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
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
