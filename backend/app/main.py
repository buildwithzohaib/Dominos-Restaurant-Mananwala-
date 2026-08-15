from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.catalog import router as catalog_router
from app.routes.inventory import router as inventory_router
from app.routes.orders import router as orders_router
from app.routes.stock_movements import router as stock_movements_router
from app.routes.dashboard import router as dashboard_router
from app.routes.products import router as products_router
from app.models import models  # noqa: F401
from app.seed import seed_data

seed_data()

app = FastAPI(title="My Restaurant POS API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(catalog_router)
app.include_router(inventory_router)
app.include_router(orders_router)
app.include_router(stock_movements_router)
app.include_router(dashboard_router)
app.include_router(products_router)

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "my-pos-api"}
