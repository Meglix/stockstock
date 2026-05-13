import sqlite3, bcrypt
from datetime import datetime, timezone
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.db import DATABASE_PATH  # noqa: E402

now = datetime.now(timezone.utc).isoformat(timespec="seconds")

def hp(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()

con = sqlite3.connect(DATABASE_PATH)
con.row_factory = sqlite3.Row
cur = con.cursor()

# Load existing roles
roles = {r["role_name"]: r["id"] for r in cur.execute("SELECT id, role_name FROM roles").fetchall()}
print("Existing roles:", roles)

# Ensure supplier role exists
if "supplier" not in roles:
    cur.execute("INSERT INTO roles (role_name, description) VALUES ('supplier', 'Supplier account')")
    roles["supplier"] = cur.lastrowid
    print("Created supplier role, id:", roles["supplier"])

# Pick first supplier_id to link the supplier test user
row = cur.execute("SELECT id FROM suppliers LIMIT 1").fetchone()
sup_id = row["id"] if row else None
print("Linking testsupplier to supplier_id:", sup_id)

users = [
    ("testuser",     "testuser@demo.local",    "Test@1234", "user",     None,   None),
    ("testadmin",    "testadmin@demo.local",    "Test@1234", "admin",    None,   None),
    ("testsupplier", "testsupplier@demo.local", "Test@1234", "supplier", sup_id, None),
]

for uname, email, pw, role, sid, sname in users:
    if cur.execute("SELECT id FROM users WHERE username=?", (uname,)).fetchone():
        print(f"  SKIP (already exists): {uname}")
        continue
    cur.execute(
        """INSERT INTO users (username,email,password_hash,role_id,supplier_id,
                              supplier_name_requested,status,is_active,created_at,updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (uname, email, hp(pw), roles[role], sid, sname, "active", 1, now, now),
    )
    print(f"  CREATED: {uname} [{role}] supplier_id={sid}")

con.commit()
con.close()
print("All done.")
