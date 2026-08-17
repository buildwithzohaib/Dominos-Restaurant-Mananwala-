"""
Tests for product image upload (Task 2.7)

Tests use a fresh in-memory database and temporary storage folder,
never touching backend/storage/images/.
"""

import tempfile
import os
from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.models import Product, Category
from app.services import image_service


@pytest.fixture(scope="function")
def engine():
    """Create a fresh in-memory SQLite engine for each test."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable foreign keys for SQLite
    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture(scope="function")
def db_session(engine):
    """Create a fresh database session and seed with test data."""
    TestSession = sessionmaker(bind=engine)
    session = TestSession()

    # Seed categories and a product
    category = Category(
        id=1,
        name_raw="Test Category",
        name_display="Test Category",
        name_key="testcategory",
        active=True,
    )
    session.add(category)

    product = Product(
        id=1,
        category_id=1,
        name_raw="Test Product",
        name_display="Test Product",
        name_key="testproduct",
        price=10000,
        stock=100,
        sku="TEST-001",
        min_stock=5,
        unit="Piece",
        purchase_price=5000,
        available=True,
    )
    session.add(product)
    session.commit()

    yield session
    session.close()


@pytest.fixture(scope="function")
def temp_storage():
    """Create a temporary storage directory and patch image_service.STORAGE_DIR."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(image_service, "STORAGE_DIR", tmpdir):
            yield tmpdir


@pytest.fixture(scope="function")
def client(db_session, temp_storage):
    """Create a TestClient with mocked database and storage."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def create_test_jpeg(width: int = 200, height: int = 150) -> bytes:
    """Create a valid JPEG image in memory."""
    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    buffer = BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


def create_test_png(width: int = 200, height: int = 150) -> bytes:
    """Create a valid PNG image in memory."""
    img = Image.new("RGB", (width, height), color=(0, 255, 0))
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def create_test_gif(width: int = 200, height: int = 150) -> bytes:
    """Create a valid GIF image in memory."""
    img = Image.new("RGB", (width, height), color=(0, 0, 255))
    buffer = BytesIO()
    img.save(buffer, format="GIF")
    return buffer.getvalue()


class TestProductImageUpload:
    """Tests for POST /api/products/{id}/image"""

    def test_upload_valid_jpeg(self, client, db_session):
        """Upload a valid JPEG image."""
        image_data = create_test_jpeg()

        response = client.post(
            "/api/products/1/image",
            files={"file": ("photo.jpg", BytesIO(image_data), "image/jpeg")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["image"] == "1.jpg"
        assert data["image_hash"] is not None
        assert len(data["image_hash"]) == 32  # MD5 hex digest

        # Verify file was saved
        db_session.refresh(db_session.query(Product).first())
        assert db_session.query(Product).first().image == "1.jpg"

    def test_upload_valid_png(self, client, db_session):
        """Upload a valid PNG image."""
        image_data = create_test_png()

        response = client.post(
            "/api/products/1/image",
            files={"file": ("photo.png", BytesIO(image_data), "image/png")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["image"] == "1.jpg"  # Saved as JPEG
        assert data["image_hash"] is not None

    def test_reject_text_file_as_jpg(self, client):
        """Reject text file sent as image."""
        text_data = b"this is not an image"

        response = client.post(
            "/api/products/1/image",
            files={"file": ("photo.jpg", BytesIO(text_data), "text/plain")},
        )

        assert response.status_code == 400
        error = response.json()
        assert "cannot" in error["detail"].lower() or "image" in error["detail"].lower()

    def test_reject_oversized_file(self, client):
        """Reject file over 2 MB."""
        # Create a file that exceeds 2 MB
        oversized_data = b"x" * (2 * 1024 * 1024 + 1)

        response = client.post(
            "/api/products/1/image",
            files={"file": ("huge.jpg", BytesIO(oversized_data), "image/jpeg")},
        )

        assert response.status_code == 400
        assert "exceeds 2 MB" in response.json()["detail"]

    def test_reject_gif_format(self, client):
        """Reject GIF even though it's a valid image (format check, not extension)."""
        gif_data = create_test_gif()

        response = client.post(
            "/api/products/1/image",
            files={"file": ("photo.gif", BytesIO(gif_data), "image/gif")},
        )

        assert response.status_code == 400
        assert "Only JPEG and PNG" in response.json()["detail"]

    def test_replace_image_changes_hash(self, client, db_session):
        """Replacing an image updates the image_hash."""
        # Upload first image
        image1 = create_test_jpeg()
        response1 = client.post(
            "/api/products/1/image",
            files={"file": ("photo.jpg", BytesIO(image1), "image/jpeg")},
        )
        hash1 = response1.json()["image_hash"]

        # Upload different image
        image2 = create_test_png()
        response2 = client.post(
            "/api/products/1/image",
            files={"file": ("photo2.png", BytesIO(image2), "image/png")},
        )
        hash2 = response2.json()["image_hash"]

        # Hashes should differ
        assert hash1 != hash2
        assert response2.json()["image"] == "1.jpg"

    def test_resize_center_crop_no_padding(self, client, db_session, temp_storage):
        """Upload 1200x600 (2:1 ratio), verify saved file is exactly 400x300 with no white padding."""
        # Create 1200x600 image (wider than 4:3 target) to force center-crop
        # Use red so we can verify no white bars exist
        large_image = Image.new("RGB", (1200, 600), color=(255, 0, 0))
        buffer = BytesIO()
        large_image.save(buffer, format="JPEG")
        image_data = buffer.getvalue()

        response = client.post(
            "/api/products/1/image",
            files={"file": ("large.jpg", BytesIO(image_data), "image/jpeg")},
        )

        assert response.status_code == 200

        # Read saved file and verify dimensions
        saved_path = os.path.join(temp_storage, "1.jpg")
        assert os.path.exists(saved_path), "Image file should exist"

        with Image.open(saved_path) as saved_img:
            # Must be exactly 400x300 (center-crop, not letterboxed)
            assert saved_img.width == 400, f"Width should be 400, got {saved_img.width}"
            assert saved_img.height == 300, f"Height should be 300, got {saved_img.height}"

            # Verify no white padding: check corners and edges
            # Sample pixels from the edge should not be pure white (255, 255, 255)
            corner_pixel = saved_img.getpixel((0, 0))
            assert corner_pixel != (255, 255, 255), f"Corner should not be white, got {corner_pixel}"

            center_pixel = saved_img.getpixel((200, 150))
            assert center_pixel != (255, 255, 255), f"Center should not be white, got {center_pixel}"

    def test_nonexistent_product(self, client):
        """Reject upload for nonexistent product."""
        image_data = create_test_jpeg()

        response = client.post(
            "/api/products/999/image",
            files={"file": ("photo.jpg", BytesIO(image_data), "image/jpeg")},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
