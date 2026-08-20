import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routes.catalog import router as catalog_router
from app.routes.categories import router as categories_router
from app.routes.customers import router as customers_router
from app.routes.inventory import router as inventory_router
from app.routes.orders import router as orders_router
from app.routes.stock_movements import router as stock_movements_router
from app.routes.dashboard import router as dashboard_router
from app.routes.products import router as products_router
from app.routes.settings import router as settings_router
from app.models import models  # noqa: F401
from app.services import image_service  # Ensure storage dir is created
from app.services.backup_service import create_backup, cleanup_old_backups
from app.database import BACKEND_DIR, DB_PATH, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: run daily backup and cleanup old backups."""
    from app.services.backup_service import get_backup_dir

    backup_dir = get_backup_dir(BACKEND_DIR)

    # Create today's backup if it doesn't already exist (file system check)
    create_backup(DB_PATH, backup_dir)

    # Clean up backups older than 30 days
    cleanup_old_backups(backup_dir, keep_days=30)

    yield
    # Shutdown: no cleanup needed for this app


app = FastAPI(title="My Restaurant POS API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(catalog_router)
app.include_router(categories_router)
app.include_router(customers_router)
app.include_router(inventory_router)
app.include_router(orders_router)
app.include_router(stock_movements_router)
app.include_router(dashboard_router)
app.include_router(products_router)
app.include_router(settings_router)

# Mount static files for product images (created at import time in image_service)
app.mount("/images", StaticFiles(directory=image_service.STORAGE_DIR), name="images")

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "my-pos-api"}
