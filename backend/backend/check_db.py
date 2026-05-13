import sqlite3, os

db_path = None
for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.db') or f.endswith('.sqlite') or f.endswith('.sqlite3'):
            db_path = os.path.join(root, f)
            print('DB found:', db_path)

if not db_path:
    print('No DB file found')
else:
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    for t in tables:
        cur.execute(f'SELECT COUNT(*) FROM "{t}"')
        n = cur.fetchone()[0]
        print(f'  {t}: {n} rows')
    con.close()
