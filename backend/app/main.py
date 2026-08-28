import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routes.auth import router as auth_router
from app.routes.catalog import router as catalog_router
from app.routes.categories import router as categories_router
from app.routes.customers import router as customers_router
from app.routes.deals import router as deals_router
from app.routes.inventory import router as inventory_router
from app.routes.orders import router as orders_router
from app.routes.stock_movements import router as stock_movements_router
from app.routes.dashboard import router as dashboard_router
from app.routes.products import router as products_router
from app.routes.settings import router as settings_router
from app.routes.users import router as users_router
from app.models import models  # noqa: F401
from app.services import image_service  # Ensure storage dir is created
from app.services.backup_service import create_backup, cleanup_old_backups, get_backup_dir
from app.services.migration_service import run_migrations, setup_file_logging
from app.database import DATA_DIR, DB_PATH, engine, get_resource_base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: set up logging, run migrations, then daily backup and cleanup old backups."""
    backup_dir = get_backup_dir(DATA_DIR)
    resource_base = get_resource_base()
    alembic_dir = Path(resource_base) / "backend" / "alembic"

    # STEP 0: Set up file logging (before anything else, so migration events are captured)
    setup_file_logging(DATA_DIR)

    # STEP 1: Run migrations first (with pre-migration backup if needed).
    # This must happen before anything else touches the database.
    try:
        run_migrations(DB_PATH, backup_dir, engine, str(alembic_dir))
    except Exception as e:
        logger.critical(f"Startup failed: {e}")
        raise

    # STEP 2: Create today's backup if it doesn't already exist (file system check)
    create_backup(DB_PATH, backup_dir)

    # STEP 3: Clean up backups older than 30 days
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
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(catalog_router)
app.include_router(categories_router)
app.include_router(customers_router)
app.include_router(deals_router)
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

# Mount built frontend assets and serve index.html for SPA routing
# CRITICAL: This must be LAST so all API routes are matched first.
# FastAPI matches routes in declaration order; the catch-all must come last.
resource_base = get_resource_base()
frontend_dist = Path(resource_base) / "frontend" / "dist"
if frontend_dist.exists():
    # Mount /assets for built assets (JS, CSS, etc.)
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    # Serve index.html for SPA routing: "/" and unknown paths return index.html
    index_html_path = frontend_dist / "index.html"

    @app.get("/")
    async def serve_root():
        return FileResponse(index_html_path)

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # If path doesn't start with /api, /images, /docs, /openapi, or /redoc, serve index.html
        if not any(path.startswith(p) for p in ["api", "images", "docs", "openapi", "redoc"]):
            return FileResponse(index_html_path)
        # Otherwise raise 404 (FastAPI will handle API routes and docs)
        raise HTTPException(status_code=404, detail="Not found")
else:
    import logging
    logging.warning(
        "Frontend dist directory not found. Run `npm run build` in frontend/ directory "
        "to build the frontend for production. Serving API only."
    )
