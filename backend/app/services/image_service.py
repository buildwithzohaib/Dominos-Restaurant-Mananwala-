"""
Image upload and processing service (Task 2.7)

Handles product image upload, validation, resizing, and storage.
"""

import os
import hashlib
from io import BytesIO
from PIL import Image, ImageOps
from fastapi import HTTPException, UploadFile
from app.database import BACKEND_DIR

# Reuse BACKEND_DIR from database.py — single source of truth for backend location
STORAGE_DIR = os.path.join(BACKEND_DIR, "storage", "images")

# Create storage directory if it does not exist
os.makedirs(STORAGE_DIR, exist_ok=True)


async def process_product_image(file: UploadFile, product_id: int) -> tuple[str, str]:
    """
    Process an uploaded product image.

    Args:
        file: UploadFile from multipart form
        product_id: Product ID to use as filename base

    Returns:
        Tuple of (filename, image_hash)
        - filename: "5.jpg" (just the filename)
        - image_hash: MD5 hex digest of the saved file

    Raises:
        HTTPException 400 on validation errors:
        - File exceeds 10 MB
        - File is not a valid image
        - Image format is not JPEG or PNG

    Notes:
        Upload limit is 10 MB (not a storage concern — resized files are 15-50 KB).
        The limit prevents obviously-broken uploads (corrupted or non-image data).
        Phone photos of food are typically 3-5 MB compressed; 10 MB is generous.
    """
    # Check file size (10 MB = 10485760 bytes)
    # Storage cost is negligible — resized images are always 15-50 KB regardless of input
    MAX_SIZE = 10 * 1024 * 1024
    content = await file.read()

    if len(content) > MAX_SIZE:
        raise HTTPException(400, "Image file exceeds 10 MB limit.")

    # Validate image using Pillow
    try:
        img = Image.open(BytesIO(content))
        # Force format detection by attempting to verify
        img.verify()
        # Reopen since verify() closes the image
        img = Image.open(BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Cannot process image file: {str(e)}")

    # Check format (must be JPEG or PNG)
    img_format = img.format  # Pillow's detected format: 'JPEG', 'PNG', etc.
    if img_format not in ("JPEG", "PNG"):
        raise HTTPException(400, f"Only JPEG and PNG images are supported. Got {img_format}.")

    # Resize and center-crop to exactly 400x300 (no white padding)
    # ImageOps.fit handles both the resize and the centre-crop in one call
    if img.mode == "RGBA":
        # Convert RGBA to RGB for JPEG (JPEG doesn't support transparency)
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[3])  # Use alpha channel as mask
        img = rgb_img

    img = ImageOps.fit(img, (400, 300), Image.Resampling.LANCZOS, centering=(0.5, 0.5))

    # Save as JPEG quality 85
    filename = f"{product_id}.jpg"
    filepath = os.path.join(STORAGE_DIR, filename)

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    saved_bytes = buffer.getvalue()

    # Write to disk
    with open(filepath, "wb") as f:
        f.write(saved_bytes)

    # Compute MD5 hash of saved file
    image_hash = hashlib.md5(saved_bytes).hexdigest()

    return filename, image_hash
