"""Stage 4 A1 — prove the partial unique index actually enforces
'at most one OPEN order per table', and nothing stricter.

Runs against a throwaway in-memory database built from the SQLAlchemy models.
NEVER touches pos.db.

Run from C:\\dev\\my-pos\\backend:
    python check_partial_index.py
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.models import Order, RestaurantTable

engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

results = []


def check(label, passed, detail=''):
    results.append((label, passed))
    print(('  PASS  ' if passed else '  FAIL  ') + label + (('  ->  ' + detail) if detail else ''))


def new_order(number, table_id, status, payment_method=None):
    return Order(
        order_number=number,
        order_type='DINE_IN',
        table_id=table_id,
        status=status,
        subtotal=1000,
        total=1000,
        payment_method=payment_method,
    )


print('=' * 70)
print('FUNCTIONAL TEST: ix_one_open_per_table')
print('=' * 70)

# --- The index must exist in a create_all() database, and be partial ---
print('\n0. Index present in the test database and partial')
with engine.connect() as conn:
    idx_sql = conn.execute(text(
        "select sql from sqlite_master where type='index' and name='ix_one_open_per_table'"
    )).scalar()
print('   ', idx_sql)
check('index exists in create_all() database', idx_sql is not None)
check("index SQL contains WHERE status = 'OPEN'",
      bool(idx_sql) and "status = 'OPEN'" in idx_sql)

session.add_all([
    RestaurantTable(id=1, name='Table 1', seats=2, active=True),
    RestaurantTable(id=2, name='Table 2', seats=4, active=True),
])
session.commit()

# --- 1. First OPEN order on table 1 ---
print('\n1. First OPEN order on table 1')
try:
    session.add(new_order('ORD-00001', 1, 'OPEN'))
    session.commit()
    check('first OPEN order accepted', True)
except Exception as ex:
    session.rollback()
    check('first OPEN order accepted', False, f'{type(ex).__name__}: {ex}')

# --- 2. Second OPEN order on table 1 must be rejected ---
print('\n2. Second OPEN order on table 1 (must be rejected)')
try:
    session.add(new_order('ORD-00002', 1, 'OPEN'))
    session.commit()
    check('second OPEN order rejected', False, 'it was accepted — index not enforcing')
except Exception as ex:
    session.rollback()
    check('second OPEN order rejected', True, type(ex).__name__)

# --- 3. OPEN order on a DIFFERENT table must succeed ---
# This is what distinguishes a correct partial index from an unconditional
# unique index on table_id.
print('\n3. OPEN order on table 2 while table 1 is still OPEN (must succeed)')
try:
    session.add(new_order('ORD-00003', 2, 'OPEN'))
    session.commit()
    check('OPEN order on a different table accepted', True)
except Exception as ex:
    session.rollback()
    check('OPEN order on a different table accepted', False, f'{type(ex).__name__}: {ex}')

# --- 4. After the first order is PAID, table 1 can be re-seated ---
print('\n4. Table 1 re-seated after its OPEN order becomes PAID (must succeed)')
try:
    first = session.query(Order).filter(Order.order_number == 'ORD-00001').one()
    first.status = 'PAID'
    first.payment_method = 'CASH'
    session.commit()
    session.add(new_order('ORD-00004', 1, 'OPEN'))
    session.commit()
    check('new OPEN order after previous one was PAID', True)
except Exception as ex:
    session.rollback()
    check('new OPEN order after previous one was PAID', False, f'{type(ex).__name__}: {ex}')

# --- 5. Many CANCELLED orders on the same table must all be allowed ---
# Another unconditional-unique-index detector.
print('\n5. Multiple CANCELLED orders on table 2 (must all succeed)')
try:
    session.add(new_order('ORD-00005', 2, 'CANCELLED'))
    session.add(new_order('ORD-00006', 2, 'CANCELLED'))
    session.commit()
    check('multiple CANCELLED orders on one table accepted', True)
except Exception as ex:
    session.rollback()
    check('multiple CANCELLED orders on one table accepted', False, f'{type(ex).__name__}: {ex}')

# --- 6. Takeaway/delivery orders have table_id NULL — many must be allowed ---
# SQLite treats NULLs as distinct in a unique index, but check it explicitly
# rather than assuming.
print('\n6. Several OPEN orders with no table (takeaway/delivery) (must succeed)')
try:
    session.add(new_order('ORD-00007', None, 'OPEN'))
    session.add(new_order('ORD-00008', None, 'OPEN'))
    session.commit()
    check('multiple OPEN orders with table_id NULL accepted', True)
except Exception as ex:
    session.rollback()
    check('multiple OPEN orders with table_id NULL accepted', False, f'{type(ex).__name__}: {ex}')

print()
print('=' * 70)
failed = [label for label, ok in results if not ok]
print(f'{len(results) - len(failed)} / {len(results)} checks passed')
if failed:
    print('FAILED:')
    for label in failed:
        print('  -', label)
else:
    print('ALL CHECKS PASSED')
print('=' * 70)
