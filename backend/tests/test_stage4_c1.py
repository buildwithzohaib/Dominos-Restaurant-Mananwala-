"""Tests for Stage 4, Task C1: HTTP endpoints for Stage 4 order services."""

import pytest
import tempfile
import os
import gc
import time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.database import Base, get_db
from app.models.models import Category, Product, RestaurantTable, Settings, Order
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
    """Create a database session for seeding."""
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


@pytest.fixture(scope="function")
def setup_test_data(db_session):
    """Seed the database with test data."""
    # Seed settings
    settings = Settings()
    db_session.add(settings)

    # Seed categories
    cat1 = Category(name_raw="Biryani", name_display="Biryani", name_key="biryani", active=True)
    db_session.add(cat1)
    db_session.flush()

    # Seed products
    prod1 = Product(
        category_id=cat1.id,
        name_raw="Chicken Biryani",
        name_display="Chicken Biryani",
        name_key="chickenbiryani",
        price=50000,
        stock=100,
        sku="BIRYANI-001",
        min_stock=1,
        unit="Portion",
        available=True,
    )
    prod2 = Product(
        category_id=cat1.id,
        name_raw="Lamb Karahi",
        name_display="Lamb Karahi",
        name_key="lambkarahi",
        price=60000,
        stock=100,
        sku="KARAHI-001",
        min_stock=1,
        unit="Portion",
        available=True,
    )
    db_session.add_all([prod1, prod2])
    db_session.flush()

    # Seed tables
    table_a = RestaurantTable(id=7, name="Patio A", seats=2, active=True)
    table_b = RestaurantTable(id=8, name="Corner Booth", seats=4, active=True)
    db_session.add_all([table_a, table_b])
    db_session.commit()

    return {
        'table_a_id': table_a.id,
        'table_b_id': table_b.id,
        'prod1_id': prod1.id,
        'prod2_id': prod2.id,
    }


def test_post_open_with_valid_table(test_client, setup_test_data):
    """POST /api/orders/open with valid table_id returns 200 with status OPEN and payment_method null."""
    response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPEN"
    assert data["payment_method"] is None


def test_post_open_duplicate_table(test_client, setup_test_data):
    """POST /api/orders/open on a table that already has an open order returns 400."""
    # Open first order
    response1 = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})
    assert response1.status_code == 200

    # Try to open second order on same table
    response2 = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})
    assert response2.status_code == 400


def test_post_items_adds_items(test_client, setup_test_data):
    """POST /api/orders/{id}/items adds items and returns updated order with items present."""
    # Open order
    open_response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})
    order_id = open_response.json()["id"]

    # Add items
    response = test_client.post(
        f"/api/orders/{order_id}/items",
        json={"items": [{"product_id": setup_test_data['prod1_id'], "quantity": 2}]}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["batch_id"] is None


def test_post_send_stamps_batch_id(test_client, setup_test_data):
    """POST /api/orders/{id}/send returns 200, items now carry a batch_id."""
    # Open order
    open_response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})
    order_id = open_response.json()["id"]

    # Add items
    test_client.post(
        f"/api/orders/{order_id}/items",
        json={"items": [{"product_id": setup_test_data['prod1_id'], "quantity": 2}]}
    )

    # Send batch
    response = test_client.post(f"/api/orders/{order_id}/send")

    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["batch_id"] == 1


def test_post_send_no_pending_items(test_client, setup_test_data):
    """POST /api/orders/{id}/send with nothing pending returns 400."""
    # Open order but don't add items
    open_response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})
    order_id = open_response.json()["id"]

    # Try to send
    response = test_client.post(f"/api/orders/{order_id}/send")

    assert response.status_code == 400


def test_post_pay_closes_order(test_client, setup_test_data):
    """POST /api/orders/{id}/pay closes the order: response status is PAID and payment_method is set."""
    # Open -> add items -> send
    open_response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})
    order_id = open_response.json()["id"]

    test_client.post(
        f"/api/orders/{order_id}/items",
        json={"items": [{"product_id": setup_test_data['prod1_id'], "quantity": 2}]}
    )

    test_client.post(f"/api/orders/{order_id}/send")

    # Pay
    response = test_client.post(
        f"/api/orders/{order_id}/pay",
        json={"payment_method": "CASH", "discount": 0, "amount_received": 100000}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PAID"
    assert data["payment_method"] == "CASH"


def test_post_pay_with_pending_items(test_client, setup_test_data):
    """POST /api/orders/{id}/pay while items are still pending returns 400."""
    # Open and add items but don't send
    open_response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})
    order_id = open_response.json()["id"]

    test_client.post(
        f"/api/orders/{order_id}/items",
        json={"items": [{"product_id": setup_test_data['prod1_id'], "quantity": 2}]}
    )

    # Try to pay without sending
    response = test_client.post(
        f"/api/orders/{order_id}/pay",
        json={"payment_method": "CASH", "discount": 0, "amount_received": 100000}
    )

    assert response.status_code == 400


def test_get_orders_with_status_open(test_client, setup_test_data):
    """GET /api/orders?status=OPEN returns open orders."""
    # Create an open order
    open_response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})
    order_id = open_response.json()["id"]

    # Query for OPEN orders
    response = test_client.get("/api/orders?status=OPEN")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(o["id"] == order_id for o in data)


def test_get_orders_status_open_excludes_paid(test_client, setup_test_data):
    """GET /api/orders?status=OPEN does NOT return an order that has been paid."""
    # Create an open order, add items, send, and pay
    open_response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})
    order_id = open_response.json()["id"]

    test_client.post(
        f"/api/orders/{order_id}/items",
        json={"items": [{"product_id": setup_test_data['prod1_id'], "quantity": 1}]}
    )

    test_client.post(f"/api/orders/{order_id}/send")

    test_client.post(
        f"/api/orders/{order_id}/pay",
        json={"payment_method": "CASH", "discount": 0, "amount_received": 50000}
    )

    # Query for OPEN orders - should not include the paid one
    response = test_client.get("/api/orders?status=OPEN")

    assert response.status_code == 200
    data = response.json()
    assert not any(o["id"] == order_id for o in data)


def test_post_items_nonexistent_order(test_client):
    """POST /api/orders/999/items returns 404."""
    response = test_client.post(
        "/api/orders/999/items",
        json={"items": [{"product_id": 1, "quantity": 1}]}
    )

    assert response.status_code == 404


def test_post_pay_nonexistent_order(test_client):
    """POST /api/orders/999/pay returns 404."""
    response = test_client.post(
        "/api/orders/999/pay",
        json={"payment_method": "CASH", "discount": 0, "amount_received": 50000}
    )

    assert response.status_code == 404


def test_full_flow_end_to_end(test_client, setup_test_data):
    """Full flow works end to end: open -> items -> send -> pay."""
    # Open
    open_response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})
    assert open_response.status_code == 200
    order_id = open_response.json()["id"]
    assert open_response.json()["status"] == "OPEN"

    # Add items
    items_response = test_client.post(
        f"/api/orders/{order_id}/items",
        json={"items": [
            {"product_id": setup_test_data['prod1_id'], "quantity": 2},
            {"product_id": setup_test_data['prod2_id'], "quantity": 1},
        ]}
    )
    assert items_response.status_code == 200
    assert len(items_response.json()["items"]) == 2
    assert all(item["batch_id"] is None for item in items_response.json()["items"])

    # Send
    send_response = test_client.post(f"/api/orders/{order_id}/send")
    assert send_response.status_code == 200
    assert all(item["batch_id"] == 1 for item in send_response.json()["items"])

    # Pay
    pay_response = test_client.post(
        f"/api/orders/{order_id}/pay",
        json={"payment_method": "CASH", "discount": 0, "amount_received": 170000}
    )
    assert pay_response.status_code == 200
    assert pay_response.json()["status"] == "PAID"
    assert pay_response.json()["payment_method"] == "CASH"


def test_post_items_has_batch_id_null(test_client, setup_test_data):
    """The JSON from POST /api/orders/{id}/items has sent_at null on each item."""
    open_response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})
    order_id = open_response.json()["id"]

    response = test_client.post(
        f"/api/orders/{order_id}/items",
        json={"items": [{"product_id": setup_test_data['prod1_id'], "quantity": 2}]}
    )

    assert response.status_code == 200
    for item in response.json()["items"]:
        assert item["batch_id"] is None
        assert item["sent_at"] is None


def test_post_send_has_sent_at(test_client, setup_test_data):
    """The JSON from POST /api/orders/{id}/send has a non-null sent_at on each item."""
    open_response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})
    order_id = open_response.json()["id"]

    test_client.post(
        f"/api/orders/{order_id}/items",
        json={"items": [{"product_id": setup_test_data['prod1_id'], "quantity": 2}]}
    )

    response = test_client.post(f"/api/orders/{order_id}/send")

    assert response.status_code == 200
    for item in response.json()["items"]:
        assert item["batch_id"] is not None
        assert item["sent_at"] is not None


def test_post_open_has_paid_at_null(test_client, setup_test_data):
    """The JSON from POST /api/orders/open has paid_at null."""
    response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})

    assert response.status_code == 200
    assert response.json()["paid_at"] is None


def test_post_pay_has_paid_at(test_client, setup_test_data):
    """The JSON from POST /api/orders/{id}/pay has a non-null paid_at."""
    open_response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})
    order_id = open_response.json()["id"]

    test_client.post(
        f"/api/orders/{order_id}/items",
        json={"items": [{"product_id": setup_test_data['prod1_id'], "quantity": 1}]}
    )

    test_client.post(f"/api/orders/{order_id}/send")

    response = test_client.post(
        f"/api/orders/{order_id}/pay",
        json={"payment_method": "CASH", "discount": 0, "amount_received": 50000}
    )

    assert response.status_code == 200
    assert response.json()["paid_at"] is not None


def test_get_order_has_paid_at_and_batch_id(test_client, setup_test_data):
    """GET /api/orders/{id} on a paid order returns paid_at and per-item batch_id."""
    open_response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})
    order_id = open_response.json()["id"]

    test_client.post(
        f"/api/orders/{order_id}/items",
        json={"items": [{"product_id": setup_test_data['prod1_id'], "quantity": 2}]}
    )

    test_client.post(f"/api/orders/{order_id}/send")

    test_client.post(
        f"/api/orders/{order_id}/pay",
        json={"payment_method": "CASH", "discount": 0, "amount_received": 100000}
    )

    # GET the order
    response = test_client.get(f"/api/orders/{order_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["paid_at"] is not None
    assert all(item["batch_id"] is not None for item in data["items"])


def test_post_open_returns_table_name(test_client, setup_test_data):
    """POST /api/orders/open returns a body where table.name equals the seeded table's name."""
    response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})

    assert response.status_code == 200
    data = response.json()
    assert data["table"] is not None
    assert data["table"]["name"] == "Patio A"
    assert data["table"]["id"] == setup_test_data['table_a_id']


def test_get_orders_open_returns_table_name(test_client, setup_test_data):
    """GET /api/orders?status=OPEN returns orders whose table.name is populated."""
    # Create an open order
    open_response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})
    order_id = open_response.json()["id"]

    # Query for OPEN orders
    response = test_client.get("/api/orders?status=OPEN")

    assert response.status_code == 200
    data = response.json()
    order = next((o for o in data if o["id"] == order_id), None)
    assert order is not None
    assert order["table"] is not None
    assert order["table"]["name"] == "Patio A"


def test_takeaway_order_has_null_table(test_client, setup_test_data):
    """A TAKEAWAY order (table_id null) returns table as null, not an error."""
    response = test_client.post(
        "/api/orders",
        json={
            "order_type": "TAKEAWAY",
            "items": [{"product_id": setup_test_data['prod1_id'], "quantity": 1}],
            "payment_method": "CASH",
            "amount_received": 50000,
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["table_id"] is None
    assert data["table"] is None


def test_table_id_still_present(test_client, setup_test_data):
    """table_id is still present in the response (it was not removed)."""
    response = test_client.post("/api/orders/open", json={"table_id": setup_test_data['table_a_id']})

    assert response.status_code == 200
    data = response.json()
    assert "table_id" in data
    assert data["table_id"] == setup_test_data['table_a_id']
