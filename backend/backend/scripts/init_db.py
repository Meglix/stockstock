from pathlib import Path
import argparse
import sqlite3
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.db import DATABASE_PATH  # noqa: E402

SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"
LEGACY_TABLES_TO_DROP = ("orders",)
LEGACY_COLUMNS_TO_DROP = {
    "users": ("store_location",),
}


def drop_legacy_columns(cursor):
    for table_name, column_names in LEGACY_COLUMNS_TO_DROP.items():
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}
        for column_name in column_names:
            if column_name in existing_columns:
                cursor.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")


def ensure_users_location_column(cursor):
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if "location_id" not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN location_id TEXT")


def main(reset: bool = False):
    # Check if schema file exists
    if not SCHEMA_PATH.exists():
        print(f"Error: schema.sql not found at {SCHEMA_PATH}")
        sys.exit(1)

    if reset and DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
        print(f"Removed existing DB: {DATABASE_PATH}")

    # Read the SQL schema
    with open(SCHEMA_PATH, "r") as f:
        schema = f.read()

    # Connect to database and execute schema
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    cursor = connection.cursor()

    try:
        cursor.executescript(schema)
        for table_name in LEGACY_TABLES_TO_DROP:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        drop_legacy_columns(cursor)
        ensure_users_location_column(cursor)
        connection.commit()
        action = "reset and initialized" if reset else "schema applied"
        print(f"Database {action} at {DATABASE_PATH}")
    except Exception as e:
        print(f"Error initializing database: {e}")
        connection.rollback()
        sys.exit(1)
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply the database schema.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the existing SQLite database first. Omit to preserve existing data.",
    )
    args = parser.parse_args()
    main(reset=args.reset)
