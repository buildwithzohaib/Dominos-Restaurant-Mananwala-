import sqlite3
c = sqlite3.connect('pos.db')
rows = c.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'").fetchall()
for r in rows:
    print(r[0])
c.close()
