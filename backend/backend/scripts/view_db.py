from pathlib import Path
import sqlite3
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.db import DATABASE_PATH  # noqa: E402


def print_table_names(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    )
    rows = cursor.fetchall()

    print("Tables in database:")
    for row in rows:
        print(f"- {row[0]}")


def table_exists(connection, table_name):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='table'
          AND name = ?
        """,
        (table_name,),
    )
    return cursor.fetchone() is not None


def print_table_count(connection, table_name):
    if not table_exists(connection, table_name):
        print(f"- {table_name}: missing")
        return

    cursor = connection.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    print(f"- {table_name}: {cursor.fetchone()[0]}")


def print_table_preview(connection, table_name, limit=5):
    if not table_exists(connection, table_name):
        print(f"\nPreview for table: {table_name}")
        print("(missing)")
        return

    cursor = connection.cursor()
    cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
    rows = cursor.fetchall()

    print(f"\nPreview for table: {table_name}")

    if len(rows) == 0:
        print("(no rows)")
        return

    column_names = [description[0] for description in cursor.description]
    print("Columns:", ", ".join(column_names))

    for row in rows:
        print(tuple(row))


def main():
    if not DATABASE_PATH.exists():
        print(f"Database file not found: {DATABASE_PATH}")
        print("Run scripts/init_db.py first.")
        return

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        print(f"Using database: {DATABASE_PATH}")
        print_table_names(connection)

        print("\nLive demo table counts:")
        count_list = [
            "users",
            "parts",
            "suppliers",
            "user_stock",
            "order_clients",
            "order_client_lines",
            "order_sales_events",
            "order_suppliers",
            "order_supplier_lines",
            "order_notification_stream",
        ]
        for table_name in count_list:
            print_table_count(connection, table_name)

        if table_exists(connection, "orders"):
            print("\nLegacy inactive table still present:")
            print_table_count(connection, "orders")

        table_list = [
            "users",
            "parts",
            "suppliers",
            "user_stock",
            "stock",
            "order_clients",
            "order_sales_events",
            "order_suppliers",
            "order_notification_stream",
        ]
        for table_name in table_list:
            print_table_preview(connection, table_name, limit=5)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
