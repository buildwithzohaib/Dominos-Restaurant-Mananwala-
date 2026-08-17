import sqlite3
c = sqlite3.connect('pos.db')
rows = c.execute('SELECT order_number, order_type, subtotal, discount, tax_rate, tax, delivery_charge, total FROM orders ORDER BY id DESC LIMIT 5').fetchall()
for r in rows:
    print(r)
