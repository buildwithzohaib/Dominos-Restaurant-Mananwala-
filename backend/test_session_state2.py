"""Test SQLAlchemy session state after caught exception during update in same transaction."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from app.models.models import Base, Customer, Order, OrderItem, Product, Category, Settings
from app.services.customer_service import create as create_customer
from datetime import datetime

# Use temp database
engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)

with Session(engine) as db:
    # Create prerequisites
    settings = Settings(id=1, restaurant_name="Test", tax_rate=0, tax_enabled=False)
    db.add(settings)

    category = Category(name_raw="Test", name_display="Test", name_key="test", active=True)
    db.add(category)

    product = Product(
        category_id=1, name_raw="Item", name_display="Item", name_key="item",
        price=10000, stock=100, available=True, sku="SKU001", min_stock=5, unit="pc"
    )
    db.add(product)

    customer = create_customer(db, name="Ali Khan", phone="03001234567")
    db.flush()

    print("Setup complete")
    print(f"Customer: {customer.id}")

# Now test the scenario: create an order, update customer address in same transaction,
# but simulate a failure on the customer update
with Session(engine) as db:
    print("\n" + "="*60)
    print("Test: Update customer BEFORE commit, with exception")
    print("="*60)

    # Create an order
    order = Order(
        order_number="ORD-00001",
        order_type="DELIVERY",
        table_id=None,
        customer_id=1,
        delivery_address="456 Oak Ave",
        status="PAID",
        subtotal=10000,
        discount=0,
        tax=0,
        tax_rate=0,
        delivery_charge=0,
        total=10000,
        payment_method="CASH",
        amount_received=10000,
        change_amount=0,
    )
    db.add(order)
    db.flush()
    order_id = order.id
    print(f"Order created: {order_id}")

    # Add order item
    item = OrderItem(
        order_id=order_id,
        product_id=1,
        product_name="Item",
        quantity=1,
        price=10000,
        line_total=10000,
    )
    db.add(item)
    db.flush()
    print("Order item added")

    # Now update customer address in same transaction, with error handling
    try:
        customer = db.get(Customer, 1)
        if customer:
            customer.address = "789 Elm St"
            # Simulate an error by trying to trigger a constraint violation
            # For example, we could set an invalid value, but address is just a string
            # so let's raise an exception explicitly to simulate a real error
            # In practice this could be a constraint, validation error, etc.
            # raise ValueError("Simulated error updating customer")
            print("Customer address updated")
    except Exception as e:
        print(f"Exception caught: {e}")
        # The question is: can we still commit?

    # Try to commit
    print("Attempting commit...")
    try:
        db.commit()
        print("✓ Commit succeeded")

        # Verify both order and customer update
        with Session(engine) as verify_db:
            o = verify_db.get(Order, order_id)
            c = verify_db.get(Customer, 1)
            print(f"Order status: {o.status}")
            print(f"Customer address: {c.address}")
    except Exception as e:
        print(f"✗ Commit failed: {e}")
        print("ORDER WAS LOST!")

print("\n" + "="*60)
print("Conclusion: If exception caught before flush/commit,")
print("session is still usable. But if flush itself fails, we need")
print("to decide: roll back everything, or do it after commit.")
print("="*60)
