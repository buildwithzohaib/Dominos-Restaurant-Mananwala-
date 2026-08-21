"""
Permission Enforcement and User Attribution Testing (Stage 7)

Tests for:
- User attribution on order operations (performed_by_user_id)
- Backward compatibility (operations without performed_by_user_id)
- Permission checking at the service level
"""

import pytest
import tempfile
import os
import gc
import time
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.database import Base
from app.models.models import User, UserSession, Order, OrderItem, Product, Category, Settings
from app.services import user_service
from app.services.order_service import create_order, cancel_order, pay_order, create_open_order, add_items_to_order, send_batch_to_kitchen
from app.schemas.schemas import OrderCreate, OrderCancelIn, PayOrderIn, OpenOrderCreate, AddItemsIn, OrderItemCreate
from fastapi import HTTPException


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


def _setup_test_data(db: Session):
    """
    Create minimal test data: owner user, category, product, and settings.
    Returns (owner_user, product).
    """
    # Create owner user
    owner = user_service.create_user(db, name="Owner", pin="1234")

    # Create settings (required for orders)
    settings = Settings(id=1, restaurant_name="Test", tax_enabled=False, tax_rate=0)
    db.add(settings)

    # Create category
    category = Category(name_raw="Test", name_display="Test", name_key="test", active=True)
    db.add(category)
    db.flush()

    # Create product
    product = Product(
        category_id=category.id,
        name_raw="Item",
        name_display="Item",
        name_key="item",
        sku="SKU001",
        price=10000,
        stock=100,
        available=True,
    )
    db.add(product)
    db.commit()

    return owner, product


class TestOrderAttribution:
    """Test user attribution (performed_by_user_id) on orders."""

    def test_create_order_records_performed_by_user_id(self, db_session):
        """create_order records performed_by_user_id when provided."""
        owner, product = _setup_test_data(db_session)

        # Create order with performed_by_user_id
        payload = OrderCreate(
            order_type="TAKEAWAY",
            table_id=None,
            customer_id=None,
            delivery_address=None,
            delivery_charge=None,
            items=[OrderItemCreate(product_id=product.id, quantity=1)],
            discount=0,
            payment_method="CASH",
            amount_received=10000,
        )

        order = create_order(db_session, payload, performed_by_user_id=owner.id)

        assert order.performed_by_user_id == owner.id
        assert order.status == "PAID"

    def test_create_order_without_performed_by_user_id(self, db_session):
        """create_order works without performed_by_user_id (backward compatibility)."""
        owner, product = _setup_test_data(db_session)

        payload = OrderCreate(
            order_type="TAKEAWAY",
            table_id=None,
            customer_id=None,
            delivery_address=None,
            delivery_charge=None,
            items=[OrderItemCreate(product_id=product.id, quantity=1)],
            discount=0,
            payment_method="CASH",
            amount_received=10000,
        )

        # Call without performed_by_user_id parameter
        order = create_order(db_session, payload)

        assert order.performed_by_user_id is None
        assert order.status == "PAID"

    def test_cancel_order_records_cancel_order_performed_by_user_id(self, db_session):
        """cancel_order records cancel_order_performed_by_user_id when provided."""
        owner, product = _setup_test_data(db_session)

        # Create an order
        payload = OrderCreate(
            order_type="TAKEAWAY",
            table_id=None,
            customer_id=None,
            delivery_address=None,
            delivery_charge=None,
            items=[OrderItemCreate(product_id=product.id, quantity=1)],
            discount=0,
            payment_method="CASH",
            amount_received=10000,
        )
        order = create_order(db_session, payload, performed_by_user_id=owner.id)

        # Cancel with performed_by_user_id
        cancel_payload = OrderCancelIn(reason="OTHER", note="Test cancellation")
        cancelled_order = cancel_order(db_session, order.id, cancel_payload, performed_by_user_id=owner.id)

        assert cancelled_order.cancel_order_performed_by_user_id == owner.id
        assert cancelled_order.status == "CANCELLED"

    def test_cancel_order_without_performed_by_user_id(self, db_session):
        """cancel_order works without performed_by_user_id (backward compatibility)."""
        owner, product = _setup_test_data(db_session)

        # Create an order
        payload = OrderCreate(
            order_type="TAKEAWAY",
            table_id=None,
            customer_id=None,
            delivery_address=None,
            delivery_charge=None,
            items=[OrderItemCreate(product_id=product.id, quantity=1)],
            discount=0,
            payment_method="CASH",
            amount_received=10000,
        )
        order = create_order(db_session, payload)

        # Cancel without performed_by_user_id parameter
        cancel_payload = OrderCancelIn(reason="OTHER", note="Test cancellation")
        cancelled_order = cancel_order(db_session, order.id, cancel_payload)

        assert cancelled_order.cancel_order_performed_by_user_id is None
        assert cancelled_order.status == "CANCELLED"

    def test_pay_order_records_performed_by_user_id(self, db_session):
        """pay_order records performed_by_user_id when provided."""
        from app.models.models import RestaurantTable

        owner, product = _setup_test_data(db_session)

        # Create a table and open order (for DINE_IN)
        table = RestaurantTable(name="Table 1", active=True)
        db_session.add(table)
        db_session.flush()

        open_payload = OpenOrderCreate(table_id=table.id, customer_id=None)
        order = create_open_order(db_session, open_payload)

        # Add items
        add_payload = AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=1)])
        order = add_items_to_order(db_session, order.id, add_payload)

        # Send to kitchen
        order = send_batch_to_kitchen(db_session, order.id)

        # Pay with performed_by_user_id
        pay_payload = PayOrderIn(discount=0, payment_method="CASH", amount_received=10000)
        paid_order = pay_order(db_session, order.id, pay_payload, performed_by_user_id=owner.id)

        assert paid_order.performed_by_user_id == owner.id
        assert paid_order.status == "PAID"

    def test_pay_order_without_performed_by_user_id(self, db_session):
        """pay_order works without performed_by_user_id (backward compatibility)."""
        from app.models.models import RestaurantTable

        owner, product = _setup_test_data(db_session)

        # Create a table and open order
        table = RestaurantTable(name="Table 2", active=True)
        db_session.add(table)
        db_session.flush()

        open_payload = OpenOrderCreate(table_id=table.id, customer_id=None)
        order = create_open_order(db_session, open_payload)

        # Add items
        add_payload = AddItemsIn(items=[OrderItemCreate(product_id=product.id, quantity=1)])
        order = add_items_to_order(db_session, order.id, add_payload)

        # Send to kitchen
        order = send_batch_to_kitchen(db_session, order.id)

        # Pay without performed_by_user_id parameter
        pay_payload = PayOrderIn(discount=0, payment_method="CASH", amount_received=10000)
        paid_order = pay_order(db_session, order.id, pay_payload)

        assert paid_order.performed_by_user_id is None
        assert paid_order.status == "PAID"


class TestRouteAuthentication:
    """Test route-level authentication requirements (Stage 7)."""

    def test_protected_endpoint_without_auth_returns_401(self):
        """A protected endpoint with no Authorization header returns 401."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.routes.auth import get_current_user_dep

        # Create a TestClient WITHOUT the autouse override
        # by temporarily clearing the override
        saved_override = app.dependency_overrides.get(get_current_user_dep)
        if get_current_user_dep in app.dependency_overrides:
            del app.dependency_overrides[get_current_user_dep]

        try:
            client = TestClient(app)

            # Try to access a protected endpoint with no Authorization header
            response = client.get("/api/orders")
            assert response.status_code == 401
            assert "Not authenticated" in response.json()["detail"]
        finally:
            # Restore the override
            if saved_override:
                app.dependency_overrides[get_current_user_dep] = saved_override

    def test_protected_endpoint_with_invalid_token_returns_401(self):
        """A protected endpoint with an invalid Bearer token returns 401."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.routes.auth import get_current_user_dep

        # Clear the override
        saved_override = app.dependency_overrides.get(get_current_user_dep)
        if get_current_user_dep in app.dependency_overrides:
            del app.dependency_overrides[get_current_user_dep]

        try:
            client = TestClient(app)

            # Try to access a protected endpoint with an invalid token
            response = client.get("/api/orders", headers={"Authorization": "Bearer invalid_token_xyz"})
            assert response.status_code == 401
        finally:
            # Restore the override
            if saved_override:
                app.dependency_overrides[get_current_user_dep] = saved_override

    def test_get_settings_without_auth_returns_200(self):
        """GET /api/settings must remain public (no authentication required)."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.routes.auth import get_current_user_dep

        # Clear the override
        saved_override = app.dependency_overrides.get(get_current_user_dep)
        if get_current_user_dep in app.dependency_overrides:
            del app.dependency_overrides[get_current_user_dep]

        try:
            client = TestClient(app)

            # GET /api/settings should succeed without Authorization header
            response = client.get("/api/settings")
            assert response.status_code == 200
            # Verify it returns a valid settings object
            data = response.json()
            assert "restaurant_name" in data
            assert "tax_rate" in data
        finally:
            # Restore the override
            if saved_override:
                app.dependency_overrides[get_current_user_dep] = saved_override
