from pathlib import Path
import csv
import sqlite3
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = BASE_DIR.parent / "data" / "raw"

sys.path.insert(0, str(BASE_DIR))

from app.db import DATABASE_PATH  # noqa: E402
from app.inventory.services.order_workflows import (  # noqa: E402
    assign_missing_part_suppliers,
    ensure_order_workflow_schema,
    seed_demo_order_workflows,
)


def parse_int(value, default=0):
    if value in (None, ""):
        return default
    return int(float(value))


def backfill_stock_quantities(connection):
    inventory_path = RAW_DATA_DIR / "inventory_snapshot.csv"
    if not inventory_path.exists():
        return 0

    part_ids = {
        row["sku"]: row["id"]
        for row in connection.execute("SELECT id, sku FROM parts").fetchall()
    }

    updated = 0
    with open(inventory_path, "r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            part_id = part_ids.get(row["sku"])
            if part_id is None:
                continue

            location_id = row.get("location_id")
            current_stock = parse_int(row.get("current_stock") or row.get("current_stock_units"), 0)
            reorder_point = parse_int(row.get("reorder_point"), 0)
            lead_time_days = parse_int(row.get("lead_time_days"), 0)

            result = connection.execute(
                """
                UPDATE stock
                SET current_stock = ?,
                    reorder_point = ?,
                    lead_time_days = ?,
                    last_updated = COALESCE(last_updated, datetime('now'))
                WHERE part_id = ?
                  AND (location = ? OR location_id = ?)
                """,
                (current_stock, reorder_point, lead_time_days, part_id, location_id, location_id),
            )
            updated += result.rowcount

    return updated


def drop_legacy_orders_table(connection):
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'orders'",
    ).fetchone()
    if exists is None:
        return None

    row_count = connection.execute("SELECT COUNT(1) FROM orders").fetchone()[0]
    connection.execute("DROP TABLE orders")
    return int(row_count or 0)


def main():
    if not DATABASE_PATH.exists():
        raise SystemExit(f"Database file not found: {DATABASE_PATH}")

    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row

    try:
        ensure_order_workflow_schema(connection)
        assign_missing_part_suppliers(connection)
        updated_stock_rows = backfill_stock_quantities(connection)
        seed_demo_order_workflows(connection, replace_existing=True)
        dropped_legacy_orders = drop_legacy_orders_table(connection)
        connection.commit()

        client_count = connection.execute("SELECT COUNT(*) FROM order_clients").fetchone()[0]
        supplier_count = connection.execute("SELECT COUNT(*) FROM order_suppliers").fetchone()[0]
        stocked_total = connection.execute("SELECT COALESCE(SUM(current_stock), 0) FROM stock").fetchone()[0]

        print(f"Order workflow tables ready.")
        print(f"Stock rows backfilled: {updated_stock_rows}")
        print(f"Client orders: {client_count}")
        print(f"Supplier orders: {supplier_count}")
        print(f"Total stock quantity: {stocked_total}")
        if dropped_legacy_orders is not None:
            print(f"Dropped legacy orders table ({dropped_legacy_orders} rows).")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
