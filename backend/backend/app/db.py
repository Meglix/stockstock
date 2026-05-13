from pathlib import Path
import os
import sqlite3

from fastapi import HTTPException


BASE_DIR = Path(__file__).resolve().parents[1]


def resolve_database_path() -> Path:
    configured_path = os.getenv("STOCK_OPTIMIZER_DB_PATH")
    if configured_path:
        path = Path(configured_path)
        return path if path.is_absolute() else BASE_DIR / path

    return BASE_DIR / "database" / "stock_optimizer.db"


DATABASE_PATH = resolve_database_path()

REQUIRED_TABLES = {
    "roles",
    "users",
    "suppliers",
    "parts",
    "stock",
    "user_stock",
    "sales_history",
    "order_sales_events",
    "order_clients",
    "order_client_lines",
    "order_suppliers",
    "order_supplier_lines",
    "order_notification_stream",
    "notifications",
}


def _db_has_required_tables() -> bool:
    if not DATABASE_PATH.exists():
        return False

    try:
        connection = sqlite3.connect(DATABASE_PATH)
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        present = {row[0] for row in cursor.fetchall()}
        return REQUIRED_TABLES.issubset(present)
    except sqlite3.Error:
        return False
    finally:
        try:
            connection.close()
        except Exception:
            pass


def bootstrap_database_if_needed() -> bool:
    # Apply schema on each startup without wiping data. Seed only when the DB is
    # missing/incomplete unless explicitly forced or CSV refresh is requested.
    auto_bootstrap = os.getenv("AUTO_BOOTSTRAP_DB", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    force_reseed = os.getenv("RESET_DB_ON_START", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    refresh_csv = os.getenv("REFRESH_CSV_ON_START", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    if not auto_bootstrap:
        return False

    database_ready = _db_has_required_tables()

    from scripts import init_db, seed_data

    if force_reseed:
        init_db.main(reset=True)
        seed_data.main(reset=True)
        return True

    init_db.main(reset=False)
    if not database_ready or refresh_csv:
        seed_data.main(reset=False)
        return True

    return False


def get_connection():
    # Create SQLite connection and expose rows as dict-like objects.
    if not DATABASE_PATH.exists():
        raise HTTPException(status_code=500, detail="Database file not found. Run scripts/init_db.py")

    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    return connection
