"""Test SQLAlchemy session state after caught exception during update."""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models.models import Base, Customer
from app.services.customer_service import create as create_customer

# Use temp database
engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)

with Session(engine) as db:
    # Create a customer
    customer = create_customer(db, name="Ali Khan", phone="03001234567")
    customer_id = customer.id

    print("Created customer:", customer.id, customer.name_display)

    # Simulate: update customer in a try-except
    try:
        c = db.get(Customer, customer_id)
        if c:
            c.address = "123 Main St"
            # Simulate an error (e.g., from validation, DB constraint, etc.)
            # In reality this would come from a flush() or attribute assignment
            # For now, just don't raise - let's test the happy path
    except Exception as e:
        print(f"Caught exception: {e}")
        db.rollback()

    # Now try to commit
    print("About to commit...")
    try:
        db.commit()
        print("✓ Commit succeeded")

        # Verify the update stuck
        c = db.query(Customer).filter(Customer.id == customer_id).first()
        print(f"Customer address after commit: {c.address}")
    except Exception as e:
        print(f"✗ Commit failed: {e}")

print("\n" + "="*60)
print("Conclusion: If no exception during update, commit works fine.")
print("But if exception occurs during flush BEFORE commit, session")
print("becomes poisoned and commit() will fail, losing the work.")
print("="*60)
