from datetime import datetime

from sqlalchemy import text

from app.database import Base, SessionLocal, engine
from app.models.models import Category, Product, RestaurantTable

DEFAULT_CATEGORIES = [
    "Fast Food",
    "Deals",
    "Drinks",
]

# NOTE on purchase_price: the original Phase 1/2 seed data never recorded an
# acquisition cost, only the POS selling price. These purchase_price values are
# clearly-labeled demo/seed data (roughly ~60% of the selling price), not real
# business figures — see the Phase 3 report. Everything else here (selling
# price, stock) reuses the exact Phase 2 values unchanged.
DEFAULT_PRODUCTS = [
    {
        "name": "Chicken Nuggets",
        "category": "Fast Food",
        "sku": "FF-NUG-001",
        "price": 25000,
        "stock": 25,
        "min_stock": 10,
        "unit": "Piece",
        "purchase_price": 15000,
    },
    {
        "name": "Regular Fries",
        "category": "Fast Food",
        "sku": "FF-FRY-001",
        "price": 15000,
        "stock": 25,
        "min_stock": 8,
        "unit": "Portion",
        "purchase_price": 9000,
    },
    {
        "name": "Zinger + Fries + Drink",
        "category": "Deals",
        "sku": "DEAL-ZFD-001",
        "price": 65000,
        "stock": 10,
        "min_stock": 5,
        "unit": "Deal",
        "purchase_price": 43000,
    },
    {
        "name": "Pepsi",
        "category": "Drinks",
        "sku": "DRK-PEP-001",
        "price": 8000,
        "stock": 25,
        "min_stock": 10,
        "unit": "Bottle",
        "purchase_price": 6000,
    },
]


def seed_data() -> None:
    db = SessionLocal()
    try:
        category_map: dict[str, int] = {}
        for name in DEFAULT_CATEGORIES:
            category = db.query(Category).filter(Category.name == name).first()
            if not category:
                category = Category(name=name, active=True)
                db.add(category)
                db.flush()
            else:
                category.active = True
            category_map[name] = category.id
        for category in db.query(Category).all():
            category.active = category.name in DEFAULT_CATEGORIES
        default_names = {item["name"] for item in DEFAULT_PRODUCTS}

        for product_info in DEFAULT_PRODUCTS:
            product = db.query(Product).filter(Product.name == product_info["name"]).first()
            if not product:
                db.add(
                    Product(
                        category_id=category_map[product_info["category"]],
                        name=product_info["name"],
                        sku=product_info["sku"],
                        price=product_info["price"],
                        stock=product_info["stock"],
                        min_stock=product_info["min_stock"],
                        unit=product_info["unit"],
                        purchase_price=product_info["purchase_price"],
                        available=product_info["stock"] > 0,
                    )
                )
            else:
                # This product row already exists — category/price/stock/available are
                # live business data at this point (POS sales, Add Stock, Inventory
                # edits all write here), so seeding must never touch them again after
                # creation. Overwriting them on every restart was silently reverting
                # completed sales and admin edits back to the hardcoded seed values;
                # only backfill the inventory fields, and only if still genuinely unset.
                if not product.sku:
                    product.sku = product_info["sku"]
                if product.min_stock is None:
                    product.min_stock = product_info["min_stock"]
                if not product.unit:
                    product.unit = product_info["unit"]
                if product.purchase_price is None:
                    product.purchase_price = product_info["purchase_price"]

        for product in db.query(Product).all():
            if product.name not in default_names:
                product.available = False
            # Backfill any legacy/non-default product that predates Phase 3 so every
            # row has a valid, unique SKU and complete inventory fields.
            if not product.sku:
                product.sku = f"SKU-{product.id:04d}"
            if product.min_stock is None:
                product.min_stock = 5
            if not product.unit:
                product.unit = "Piece"
            if product.purchase_price is None:
                product.purchase_price = 0
            if product.updated_at is None:
                product.updated_at = datetime.utcnow()

        if db.query(RestaurantTable).count() == 0:
            db.add_all(
                [
                    RestaurantTable(name=f"Table {i}", seats=2 if i < 3 else 4)
                    for i in range(1, 7)
                ]
            )

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
