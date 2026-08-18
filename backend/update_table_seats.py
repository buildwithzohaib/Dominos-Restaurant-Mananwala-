"""
Update all restaurant table seats to 6.

This script uses SQLAlchemy to safely update the seats column for all active
tables in the database. It prints the before/after state of each table for
verification, and does not modify any other tables or settings.

Usage:
    python update_table_seats.py
"""

import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import RestaurantTable

# Database connection (matches app/database.py configuration)
DATABASE_URL = "sqlite:///./pos.db"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def main():
    session = SessionLocal()
    try:
        # Fetch all active tables
        tables = session.query(RestaurantTable).filter(
            RestaurantTable.active.is_(True)
        ).all()

        if not tables:
            print("No active tables found.")
            return

        print(f"Updating {len(tables)} table(s) to 6 seats...\n")

        # Update each table and print before/after
        for table in tables:
            old_seats = table.seats
            table.seats = 6
            print(f"  {table.name}: {old_seats} seats → 6 seats")

        # Commit the transaction
        session.commit()
        print(f"\n✓ Successfully updated all {len(tables)} table(s).")

    except Exception as e:
        session.rollback()
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
