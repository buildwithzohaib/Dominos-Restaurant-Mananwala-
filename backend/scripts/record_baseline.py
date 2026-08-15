#!/usr/bin/env python
"""Record baseline sums and counts before money migration."""

import json
from decimal import Decimal
from sqlalchemy import func, text
from app.database import SessionLocal
from app.models.models import Product, Order, OrderItem, StockMovement

db = SessionLocal()

baseline = {}

# Products
products_count = db.query(Product).count()
price_sum = db.query(func.sum(Product.price)).scalar() or Decimal("0")
purchase_price_sum = db.query(func.sum(Product.purchase_price)).scalar() or Decimal("0")

baseline["products"] = {
    "count": products_count,
    "price_sum": str(price_sum),
    "purchase_price_sum": str(purchase_price_sum),
}

# Orders
orders_count = db.query(Order).count()
subtotal_sum = db.query(func.sum(Order.subtotal)).scalar() or Decimal("0")
discount_sum = db.query(func.sum(Order.discount)).scalar() or Decimal("0")
tax_sum = db.query(func.sum(Order.tax)).scalar() or Decimal("0")
total_sum = db.query(func.sum(Order.total)).scalar() or Decimal("0")
amount_received_sum = db.query(func.sum(Order.amount_received)).scalar() or Decimal("0")
change_amount_sum = db.query(func.sum(Order.change_amount)).scalar() or Decimal("0")

baseline["orders"] = {
    "count": orders_count,
    "subtotal_sum": str(subtotal_sum),
    "discount_sum": str(discount_sum),
    "tax_sum": str(tax_sum),
    "total_sum": str(total_sum),
    "amount_received_sum": str(amount_received_sum),
    "change_amount_sum": str(change_amount_sum),
}

# OrderItems
orderitems_count = db.query(OrderItem).count()
price_sum_oi = db.query(func.sum(OrderItem.price)).scalar() or Decimal("0")
line_total_sum_oi = db.query(func.sum(OrderItem.line_total)).scalar() or Decimal("0")

baseline["order_items"] = {
    "count": orderitems_count,
    "price_sum": str(price_sum_oi),
    "line_total_sum": str(line_total_sum_oi),
}

# StockMovements
stockmov_count = db.query(StockMovement).count()
purchase_price_sum_sm = db.query(func.sum(StockMovement.purchase_price)).scalar() or Decimal("0")

baseline["stock_movements"] = {
    "count": stockmov_count,
    "purchase_price_sum": str(purchase_price_sum_sm),
}

# Write to file
with open("baseline_sums.json", "w") as f:
    json.dump(baseline, f, indent=2)

print("\nBASELINE RECORDED to baseline_sums.json")
print(json.dumps(baseline, indent=2))

db.close()
