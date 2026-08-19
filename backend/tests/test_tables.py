"""
Table Management Testing Suite (Phase 11)

Comprehensive tests for table CRUD, soft delete, and dine-in order integration.
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
from app.models.models import RestaurantTable, Order
from app.main import app


@pytest.fixture(scope="function")
def engine():
    """Create a fresh temporary SQLite engine for each test."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    test_engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(bind=test_engine)

    yield test_engine

    test_engine.dispose()
    gc.collect()
    time.sleep(0.1)

    for _ in range(5):
        try:
            os.remove(db_path)
            break
        except OSError:
            time.sleep(0.1)


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

class TestTableCreate:
    """Table creation and validation tests."""

    def test_create_table_with_name_only(self, test_client):
        """Create table with name only -> seats defaults to 6, active=True"""
        response = test_client.post("/api/tables", json={"name": "Table 1"})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Table 1"
        assert data["seats"] == 6
        assert data["active"] is True
        assert data["id"] == 1

    def test_create_table_normalizes_whitespace(self, test_client):
        """Create table with extra whitespace -> normalized"""
        response = test_client.post("/api/tables", json={"name": "  Table  1  "})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Table 1"

    def test_create_two_tables_with_different_names(self, test_client):
        """Create two tables with different names -> both succeed"""
        response1 = test_client.post("/api/tables", json={"name": "Table 1"})
        response2 = test_client.post("/api/tables", json={"name": "Table 2"})
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json()["id"] != response2.json()["id"]

    def test_create_table_duplicate_name_fails_400(self, test_client):
        """Create table with duplicate name -> 400 error"""
        test_client.post("/api/tables", json={"name": "Table 1"})
        response = test_client.post("/api/tables", json={"name": "Table 1"})
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_table_duplicate_name_case_insensitive_fails_400(self, test_client):
        """Create table with name differing only by case -> 400 error"""
        test_client.post("/api/tables", json={"name": "Table 1"})
        response = test_client.post("/api/tables", json={"name": "table 1"})
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_table_duplicate_case_insensitive_with_inactive_fails_informatively(self, test_client):
        """Create table with name of inactive table -> 400 error indicating inactive status with structured id"""
        # Create two tables (so we can deactivate one without hitting the "last active" constraint)
        response1 = test_client.post("/api/tables", json={"name": "Table 1"})
        table1_id = response1.json()["id"]
        test_client.post("/api/tables", json={"name": "Table 2"})

        # Deactivate Table 1
        deactivate_response = test_client.patch(f"/api/tables/{table1_id}/deactivate")
        assert deactivate_response.status_code == 200, "Deactivate should succeed when other tables exist"
        assert deactivate_response.json()["active"] is False

        # Try to create with same name (case-insensitive)
        response = test_client.post("/api/tables", json={"name": "table 1"})
        assert response.status_code == 400
        detail = response.json()["detail"]
        # Error response is a dict with message and inactive_table_id (Rule 2: id not in message)
        assert isinstance(detail, dict), "Error detail should be a dict with message and inactive_table_id"
        assert "inactive" in detail["message"].lower()
        assert detail["inactive_table_id"] == table1_id
        # Verify the message itself does NOT contain ID-exposition patterns (Rule 2)
        assert "ID:" not in detail["message"], "Message should not expose database ID with 'ID:' pattern"

    def test_create_table_empty_name_fails_400(self, test_client):
        """Create table with empty name -> 400 error from service validation"""
        response = test_client.post("/api/tables", json={"name": ""})
        assert response.status_code == 400
        assert "required" in response.json()["detail"].lower()

    def test_create_table_whitespace_only_name_fails_400(self, test_client):
        """Create table with whitespace-only name -> 400 error"""
        response = test_client.post("/api/tables", json={"name": "   "})
        assert response.status_code == 400


# ============================================================================
# RENAME TESTS
# ============================================================================

class TestTableRename:
    """Table rename and validation tests."""

    def test_rename_table_to_new_name(self, test_client):
        """Rename table to a new name -> succeeds"""
        response = test_client.post("/api/tables", json={"name": "Old Name"})
        table_id = response.json()["id"]

        response = test_client.put(f"/api/tables/{table_id}", json={"name": "New Name"})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["id"] == table_id

    def test_rename_table_to_own_name_same_case_succeeds(self, test_client):
        """Rename table to its own name (same case) -> succeeds without error"""
        response = test_client.post("/api/tables", json={"name": "Table 1"})
        table_id = response.json()["id"]

        response = test_client.put(f"/api/tables/{table_id}", json={"name": "Table 1"})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Table 1"

    def test_rename_table_to_own_name_different_case_succeeds(self, test_client):
        """Rename table to own name but different case -> succeeds, normalizes to new case.

        This is intentional: allows incremental corrections like "TABLE 1" -> "Table 1"
        without requiring a completely different name. The duplicate check excludes self
        so case-only changes are permitted.
        """
        response = test_client.post("/api/tables", json={"name": "Table 1"})
        table_id = response.json()["id"]

        response = test_client.put(f"/api/tables/{table_id}", json={"name": "table 1"})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "table 1"  # Normalized to provided case

    def test_rename_table_to_duplicate_name_fails_400(self, test_client):
        """Rename table to name of another active table -> 400 error"""
        response1 = test_client.post("/api/tables", json={"name": "Table 1"})
        response2 = test_client.post("/api/tables", json={"name": "Table 2"})
        table_id = response2.json()["id"]

        response = test_client.put(f"/api/tables/{table_id}", json={"name": "Table 1"})
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_rename_table_to_name_of_inactive_table_fails_informatively(self, test_client):
        """Rename table to name of inactive table -> 400 error indicating inactive status with structured id"""
        # Create two tables
        response1 = test_client.post("/api/tables", json={"name": "Table 1"})
        table1_id = response1.json()["id"]
        response2 = test_client.post("/api/tables", json={"name": "Table 2"})
        table2_id = response2.json()["id"]

        # Deactivate Table 1
        test_client.patch(f"/api/tables/{table1_id}/deactivate")

        # Try to rename Table 2 to Table 1's name
        response = test_client.put(f"/api/tables/{table2_id}", json={"name": "Table 1"})
        assert response.status_code == 400
        detail = response.json()["detail"]
        # Error response is a dict with message and inactive_table_id (Rule 2: id not in message)
        assert isinstance(detail, dict), "Error detail should be a dict with message and inactive_table_id"
        assert "inactive" in detail["message"].lower()
        assert detail["inactive_table_id"] == table1_id
        # Verify message doesn't contain ID-exposition patterns (Rule 2: id goes in structured data)
        # A bare digit in the table name is OK (e.g., "Table 1"), but patterns like "ID:" or "(id"
        # would indicate the id was exposed in the message.
        assert "ID:" not in detail["message"], "Message should not expose database ID with 'ID:' pattern"
        assert "(id" not in detail["message"].lower(), "Message should not expose database ID with '(id' pattern"

    def test_rename_nonexistent_table_returns_404(self, test_client):
        """Rename non-existent table -> 404 error"""
        response = test_client.put("/api/tables/9999", json={"name": "New Name"})
        assert response.status_code == 404

    def test_rename_normalizes_whitespace(self, test_client):
        """Rename table with extra whitespace -> normalized"""
        response = test_client.post("/api/tables", json={"name": "Table 1"})
        table_id = response.json()["id"]

        response = test_client.put(f"/api/tables/{table_id}", json={"name": "  Table  2  "})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Table 2"


# ============================================================================
# DEACTIVATE TESTS
# ============================================================================

class TestTableDeactivate:
    """Table deactivation (soft delete) tests."""

    def test_deactivate_active_table_succeeds(self, test_client):
        """Deactivate an active table -> succeeds when other active tables exist"""
        # Create two tables so there's at least one remaining active
        response1 = test_client.post("/api/tables", json={"name": "Table 1"})
        response2 = test_client.post("/api/tables", json={"name": "Table 2"})
        table_id = response2.json()["id"]

        response = test_client.patch(f"/api/tables/{table_id}/deactivate")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is False

    def test_deactivate_table_with_open_order_fails_400(self, test_client, db_session):
        """Deactivate table with OPEN order -> 400 error naming the table"""
        # Create table
        response = test_client.post("/api/tables", json={"name": "Table 1"})
        table_id = response.json()["id"]

        # Create OPEN order on that table
        order = Order(
            order_number="ORD-001",
            order_type="DINE_IN",
            table_id=table_id,
            status="OPEN",
            subtotal=1000,
            total=1000
        )
        db_session.add(order)
        db_session.commit()

        # Try to deactivate
        response = test_client.patch(f"/api/tables/{table_id}/deactivate")
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "Table 1" in detail  # Must name the table, not the ID
        assert "open order" in detail.lower()

    def test_deactivate_last_active_table_fails_400(self, test_client):
        """Deactivate the last active table -> 400 error"""
        # Create one table (it's the only one, so the last active)
        response = test_client.post("/api/tables", json={"name": "Table 1"})
        table_id = response.json()["id"]

        # Try to deactivate
        response = test_client.patch(f"/api/tables/{table_id}/deactivate")
        assert response.status_code == 400
        assert "last active table" in response.json()["detail"].lower()

    def test_deactivate_one_of_many_tables_succeeds(self, test_client):
        """Deactivate one table when multiple active tables exist -> succeeds"""
        # Create two tables
        response1 = test_client.post("/api/tables", json={"name": "Table 1"})
        table1_id = response1.json()["id"]
        response2 = test_client.post("/api/tables", json={"name": "Table 2"})

        # Deactivate Table 1
        response = test_client.patch(f"/api/tables/{table1_id}/deactivate")
        assert response.status_code == 200
        assert response.json()["active"] is False

    def test_deactivate_already_inactive_table_fails_400(self, test_client):
        """Deactivate an already-inactive table -> 400 error"""
        # Create two tables
        test_client.post("/api/tables", json={"name": "Table 1"})
        response = test_client.post("/api/tables", json={"name": "Table 2"})
        table_id = response.json()["id"]

        # Deactivate
        test_client.patch(f"/api/tables/{table_id}/deactivate")

        # Try to deactivate again
        response = test_client.patch(f"/api/tables/{table_id}/deactivate")
        assert response.status_code == 400
        assert "already inactive" in response.json()["detail"]

    def test_deactivate_nonexistent_table_returns_404(self, test_client):
        """Deactivate non-existent table -> 404 error"""
        response = test_client.patch("/api/tables/9999/deactivate")
        assert response.status_code == 404


# ============================================================================
# ACTIVATE TESTS
# ============================================================================

class TestTableActivate:
    """Table activation (restore) tests."""

    def test_activate_inactive_table_succeeds(self, test_client):
        """Activate an inactive table -> succeeds"""
        # Create two tables (to avoid "last active" constraint)
        response1 = test_client.post("/api/tables", json={"name": "Table 1"})
        response2 = test_client.post("/api/tables", json={"name": "Table 2"})
        table_id = response2.json()["id"]

        # Deactivate Table 2
        test_client.patch(f"/api/tables/{table_id}/deactivate")

        # Activate Table 2
        response = test_client.patch(f"/api/tables/{table_id}/activate")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is True

    def test_activate_already_active_table_fails_400(self, test_client):
        """Activate an already-active table -> 400 error"""
        response = test_client.post("/api/tables", json={"name": "Table 1"})
        table_id = response.json()["id"]

        # Try to activate (already active)
        response = test_client.patch(f"/api/tables/{table_id}/activate")
        assert response.status_code == 400
        assert "already active" in response.json()["detail"]

    def test_activate_nonexistent_table_returns_404(self, test_client):
        """Activate non-existent table -> 404 error"""
        response = test_client.patch("/api/tables/9999/activate")
        assert response.status_code == 404


# ============================================================================
# LIST / FILTER TESTS
# ============================================================================

class TestTableList:
    """Table list and filtering tests."""

    def test_list_tables_no_parameter_returns_active_only(self, test_client):
        """List tables without parameter -> returns only active tables"""
        # Create two tables
        test_client.post("/api/tables", json={"name": "Table 1"})
        response2 = test_client.post("/api/tables", json={"name": "Table 2"})
        table2_id = response2.json()["id"]

        # Deactivate Table 2
        test_client.patch(f"/api/tables/{table2_id}/deactivate")

        # List without parameter
        response = test_client.get("/api/tables")
        assert response.status_code == 200
        tables = response.json()
        assert len(tables) == 1
        assert tables[0]["name"] == "Table 1"

    def test_list_tables_include_inactive_false_explicit(self, test_client):
        """List with include_inactive=false -> returns only active tables"""
        # Create and deactivate a table
        response1 = test_client.post("/api/tables", json={"name": "Table 1"})
        response2 = test_client.post("/api/tables", json={"name": "Table 2"})
        table2_id = response2.json()["id"]
        test_client.patch(f"/api/tables/{table2_id}/deactivate")

        # List with include_inactive=false
        response = test_client.get("/api/tables?include_inactive=false")
        assert response.status_code == 200
        tables = response.json()
        assert len(tables) == 1

    def test_list_tables_include_inactive_true_returns_all(self, test_client):
        """List with include_inactive=true -> returns all tables"""
        # Create and deactivate a table
        response1 = test_client.post("/api/tables", json={"name": "Table 1"})
        response2 = test_client.post("/api/tables", json={"name": "Table 2"})
        table2_id = response2.json()["id"]
        test_client.patch(f"/api/tables/{table2_id}/deactivate")

        # List with include_inactive=true
        response = test_client.get("/api/tables?include_inactive=true")
        assert response.status_code == 200
        tables = response.json()
        assert len(tables) == 2
        # Verify one is active and one is inactive
        active_count = sum(1 for t in tables if t["active"])
        inactive_count = sum(1 for t in tables if not t["active"])
        assert active_count == 1
        assert inactive_count == 1

    def test_list_tables_empty_returns_empty_list(self, test_client):
        """List tables when none exist -> returns empty list"""
        response = test_client.get("/api/tables")
        assert response.status_code == 200
        tables = response.json()
        assert tables == []

    def test_list_tables_sorted_by_id(self, test_client):
        """List tables -> sorted by id"""
        test_client.post("/api/tables", json={"name": "Table B"})
        test_client.post("/api/tables", json={"name": "Table A"})
        test_client.post("/api/tables", json={"name": "Table C"})

        response = test_client.get("/api/tables")
        tables = response.json()
        ids = [t["id"] for t in tables]
        assert ids == sorted(ids)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestTableIntegration:
    """Integration tests combining multiple operations."""

    def test_create_deactivate_reactivate_cycle(self, test_client):
        """Create table -> deactivate -> activate -> verify states"""
        # Create
        response = test_client.post("/api/tables", json={"name": "Table 1"})
        table_id = response.json()["id"]
        assert response.json()["active"] is True

        # Create second table to avoid "last active" constraint
        test_client.post("/api/tables", json={"name": "Table 2"})

        # Deactivate
        response = test_client.patch(f"/api/tables/{table_id}/deactivate")
        assert response.json()["active"] is False

        # Activate
        response = test_client.patch(f"/api/tables/{table_id}/activate")
        assert response.json()["active"] is True

    def test_rename_after_deactivate_restore_cycle(self, test_client):
        """Deactivate table, rename it, restore it -> name persists"""
        # Create two tables
        test_client.post("/api/tables", json={"name": "Table 1"})
        response = test_client.post("/api/tables", json={"name": "Table 2"})
        table_id = response.json()["id"]

        # Deactivate
        test_client.patch(f"/api/tables/{table_id}/deactivate")

        # Rename while inactive
        response = test_client.put(f"/api/tables/{table_id}", json={"name": "Renamed Table"})
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed Table"

        # Activate
        response = test_client.patch(f"/api/tables/{table_id}/activate")
        assert response.json()["name"] == "Renamed Table"
