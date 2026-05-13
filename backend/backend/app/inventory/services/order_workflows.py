from __future__ import annotations

from datetime import datetime, timedelta
import random
import sqlite3

from fastapi import HTTPException

from app.inventory.schemas.orders import (
    ClientOrderCreatePayload,
    SupplierOrderCreatePayload,
    WorkflowOrderLinePayload,
)
from app.inventory.services.user_stock import change_user_stock_quantity, ensure_user_stock_schema


CLIENT_STATUSES = ("Pending", "Approved", "Denied", "Scheduled", "Delivered")
SUPPLIER_STATUSES = ("Pending", "Approved", "Delivered", "Delayed", "Refused", "Received")
MANUAL_SUPPLIER_DELIVERY_SECONDS = 30
INCOMING_ORDER_INTERVAL_SECONDS = 60
MAX_ACTIVE_INCOMING_ORDERS = 6

CATEGORY_SUPPLIER_MAP = {
    "winter_fluids": "SUP-FLUIDS-EU",
    "coolant": "SUP-FLUIDS-EU",
    "consumables": "SUP-FLUIDS-EU",
    "wipers": "SUP-ACCESS-EU",
    "accessories": "SUP-ACCESS-EU",
    "battery": "SUP-ELECTRIC-DE",
    "lighting": "SUP-ELECTRIC-DE",
    "filters": "SUP-FILTERS-FR",
    "maintenance": "SUP-MAINT-DE",
    "brakes": "SUP-BRAKES-IT",
    "ac_cooling": "SUP-CLIMATE-ES",
    "tires": "SUP-TIRES-PL",
}

ORDER_WORKFLOW_DDL = """
CREATE TABLE IF NOT EXISTS order_clients (
    id TEXT PRIMARY KEY,
    client_name TEXT NOT NULL,
    user_id INTEGER,
    location TEXT NOT NULL,
    requested_time TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending'
        CHECK (status IN ('Pending','Approved','Denied','Scheduled','Delivered')),
    fulfillment_status TEXT NOT NULL DEFAULT 'unreviewed'
        CHECK (fulfillment_status IN ('unreviewed','ready','partial','backorder','fulfilled','denied')),
    scheduled_for TEXT,
    stock_applied INTEGER NOT NULL DEFAULT 0 CHECK (stock_applied IN (0, 1)),
    shortage_quantity INTEGER NOT NULL DEFAULT 0 CHECK (shortage_quantity >= 0),
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS order_client_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    part_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    part_name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    allocated_quantity INTEGER NOT NULL DEFAULT 0 CHECK (allocated_quantity >= 0),
    shortage_quantity INTEGER NOT NULL DEFAULT 0 CHECK (shortage_quantity >= 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    FOREIGN KEY (order_id) REFERENCES order_clients(id) ON DELETE CASCADE,
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS order_sales_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_client_id TEXT NOT NULL,
    order_client_line_id INTEGER NOT NULL UNIQUE,
    user_id INTEGER,
    part_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    part_name TEXT NOT NULL,
    category TEXT,
    location TEXT NOT NULL,
    quantity_sold INTEGER NOT NULL CHECK (quantity_sold >= 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    revenue_eur REAL NOT NULL CHECK (revenue_eur >= 0),
    sold_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (order_client_id) REFERENCES order_clients(id) ON DELETE CASCADE,
    FOREIGN KEY (order_client_line_id) REFERENCES order_client_lines(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS order_suppliers (
    id TEXT PRIMARY KEY,
    supplier_id TEXT,
    supplier_name TEXT NOT NULL,
    user_id INTEGER,
    location TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending'
        CHECK (status IN ('Pending','Approved','Delivered','Delayed','Refused','Received')),
    estimated_arrival TEXT NOT NULL,
    postponed_until TEXT,
    received_at TEXT,
    source_client_order_id TEXT,
    stock_applied INTEGER NOT NULL DEFAULT 0 CHECK (stock_applied IN (0, 1)),
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS order_supplier_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    part_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    part_name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    received_quantity INTEGER NOT NULL DEFAULT 0 CHECK (received_quantity >= 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    FOREIGN KEY (order_id) REFERENCES order_suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_order_clients_status ON order_clients(status);
CREATE INDEX IF NOT EXISTS idx_order_clients_location ON order_clients(location);
CREATE INDEX IF NOT EXISTS idx_order_client_lines_order ON order_client_lines(order_id);
CREATE INDEX IF NOT EXISTS idx_order_sales_events_user_sold_at ON order_sales_events(user_id, sold_at);
CREATE INDEX IF NOT EXISTS idx_order_sales_events_category_sold_at ON order_sales_events(category, sold_at);
CREATE INDEX IF NOT EXISTS idx_order_suppliers_status ON order_suppliers(status);
CREATE INDEX IF NOT EXISTS idx_order_suppliers_supplier ON order_suppliers(supplier_id);
CREATE INDEX IF NOT EXISTS idx_order_supplier_lines_order ON order_supplier_lines(order_id);

CREATE TABLE IF NOT EXISTS order_notification_stream (
    user_id INTEGER PRIMARY KEY,
    last_generated_at TEXT NOT NULL,
    next_kind TEXT NOT NULL DEFAULT 'client'
        CHECK (next_kind IN ('client','supplier')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def ensure_order_workflow_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(ORDER_WORKFLOW_DDL)
    ensure_order_workflow_columns(connection)
    normalize_supplier_delivery_state(connection)
    assign_missing_part_suppliers(connection)
    connection.commit()


def ensure_order_workflow_columns(connection: sqlite3.Connection) -> None:
    column_defs = {
        "order_clients": {
            "fulfillment_status": "TEXT NOT NULL DEFAULT 'unreviewed'",
            "shortage_quantity": "INTEGER NOT NULL DEFAULT 0",
            "notes": "TEXT",
        },
        "order_client_lines": {
            "allocated_quantity": "INTEGER NOT NULL DEFAULT 0",
            "shortage_quantity": "INTEGER NOT NULL DEFAULT 0",
        },
        "order_suppliers": {
            "source_client_order_id": "TEXT",
            "notes": "TEXT",
        },
        "order_supplier_lines": {
            "received_quantity": "INTEGER NOT NULL DEFAULT 0",
        },
    }

    for table_name, definitions in column_defs.items():
        existing = {
            row["name"] if isinstance(row, sqlite3.Row) else row[1]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for column_name, ddl in definitions.items():
            if column_name not in existing:
                connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")


def normalize_supplier_delivery_state(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        UPDATE order_suppliers
        SET status = 'Received'
        WHERE status = 'Delivered'
          AND stock_applied = 1
        """
    )
    connection.execute(
        """
        UPDATE order_suppliers
        SET received_at = NULL
        WHERE status = 'Delivered'
          AND stock_applied = 0
        """
    )


def assign_missing_part_suppliers(connection: sqlite3.Connection) -> None:
    for category, supplier_id in CATEGORY_SUPPLIER_MAP.items():
        connection.execute(
            """
            UPDATE parts
            SET supplier_id = ?
            WHERE category = ?
              AND supplier_id IS NULL
              AND EXISTS (SELECT 1 FROM suppliers WHERE id = ?)
            """,
            (supplier_id, category, supplier_id),
        )

    fallback = connection.execute("SELECT id FROM suppliers ORDER BY id LIMIT 1").fetchone()
    if fallback is not None:
        fallback_id = fallback["id"] if isinstance(fallback, sqlite3.Row) else fallback[0]
        connection.execute(
            "UPDATE parts SET supplier_id = ? WHERE supplier_id IS NULL",
            (fallback_id,),
        )


def make_order_id(prefix: str) -> str:
    return f"{prefix}-{random.randint(1000, 9999)}"


def get_part_for_order(
    connection: sqlite3.Connection,
    *,
    part_id: int | None = None,
    sku: str | None = None,
    location: str | None = None,
    current_user: dict | None = None,
) -> sqlite3.Row | None:
    filters = []
    params: list[object] = []

    if part_id is not None:
        filters.append("p.id = ?")
        params.append(part_id)
    if sku is not None:
        filters.append("p.sku = ?")
        params.append(sku)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    part = connection.execute(
        f"""
        SELECT
            p.id AS part_id,
            p.sku,
            p.part_name,
            p.unit_price,
            p.lead_time_days,
            p.supplier_id,
            s.supplier_name
        FROM parts p
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        {where_clause}
        LIMIT 1
        """,
        params,
    ).fetchone()

    if part is None:
        return None

    selected_location = location
    current_stock = 0
    location_id = None
    if current_user and current_user.get("id"):
        ensure_user_stock_schema(connection)
        stock = connection.execute(
            """
            SELECT location, location_id, current_stock
            FROM user_stock
            WHERE user_id = ? AND part_id = ?
            """,
            (current_user["id"], part["part_id"]),
        ).fetchone()
        if stock:
            selected_location = selected_location or stock["location"]
            location_id = stock["location_id"]
            current_stock = int(stock["current_stock"] or 0)

    selected_location = selected_location or (current_user or {}).get("company") or "My Store"
    return {
        **dict(part),
        "location": selected_location,
        "location_id": location_id,
        "current_stock": current_stock,
    }


def parse_clock_time(time_value: str | None) -> str:
    now = datetime.now().astimezone()
    if not time_value:
        return (now + timedelta(hours=1)).isoformat(timespec="seconds")

    try:
        hours_text, minutes_text = time_value.split(":", 1)
        hours = int(hours_text)
        minutes = int(minutes_text)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="time must use HH:MM format") from error

    scheduled = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
    if scheduled <= now:
        scheduled = scheduled + timedelta(days=1)
    return scheduled.isoformat(timespec="seconds")


def fetch_client_order(connection: sqlite3.Connection, order_id: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM order_clients WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Client order not found")
    return row


def fetch_supplier_order(connection: sqlite3.Connection, order_id: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM order_suppliers WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Supplier order not found")
    return row


def resolve_order_lines(
    connection: sqlite3.Connection,
    items: list[WorkflowOrderLinePayload],
    location: str | None,
    current_user: dict,
) -> tuple[str | None, list[tuple[sqlite3.Row, int]]]:
    resolved = []
    selected_location = location

    for item in items:
        part = get_part_for_order(
            connection,
            part_id=item.part_id,
            sku=item.sku.strip() if item.sku else None,
            location=selected_location,
            current_user=current_user,
        )
        if part is None:
            raise HTTPException(status_code=404, detail="Part or stock record not found")
        if selected_location is None:
            selected_location = part["location"]
        resolved.append((part, item.quantity))

    return selected_location, resolved


def create_client_order_record(
    connection: sqlite3.Connection,
    payload: ClientOrderCreatePayload,
    current_user: dict,
) -> dict:
    ensure_order_workflow_schema(connection)
    location, resolved_lines = resolve_order_lines(connection, payload.items, payload.location, current_user)
    if location is None:
        raise HTTPException(status_code=400, detail="Order location could not be resolved")

    now = utc_now_iso()
    order_id = make_order_id("CL")
    while connection.execute("SELECT 1 FROM order_clients WHERE id = ?", (order_id,)).fetchone():
        order_id = make_order_id("CL")

    connection.execute(
        """
        INSERT INTO order_clients (
            id, client_name, user_id, location, requested_time, status,
            fulfillment_status, scheduled_for, stock_applied, shortage_quantity,
            notes, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, 'Pending', 'unreviewed', NULL, 0, 0, NULL, ?, ?)
        """,
        (
            order_id,
            payload.client_name.strip(),
            current_user.get("id"),
            location,
            payload.requested_time or datetime.utcnow().strftime("%H:%M"),
            now,
            now,
        ),
    )

    for part, quantity in resolved_lines:
        connection.execute(
            """
            INSERT INTO order_client_lines (
                order_id, part_id, sku, part_name, quantity,
                allocated_quantity, shortage_quantity, unit_price
            )
            VALUES (?, ?, ?, ?, ?, 0, 0, ?)
            """,
            (order_id, part["part_id"], part["sku"], part["part_name"], quantity, part["unit_price"]),
        )

    connection.commit()
    return client_order_to_dict(connection, fetch_client_order(connection, order_id))


def create_supplier_order_record(
    connection: sqlite3.Connection,
    payload: SupplierOrderCreatePayload,
    current_user: dict,
) -> dict:
    ensure_order_workflow_schema(connection)
    location, resolved_lines = resolve_order_lines(connection, payload.items, payload.location, current_user)
    if location is None:
        raise HTTPException(status_code=400, detail="Order location could not be resolved")

    supplier_id = payload.supplier_id or resolved_lines[0][0]["supplier_id"]
    if not supplier_id:
        raise HTTPException(status_code=400, detail="Supplier could not be resolved for the order")

    supplier = connection.execute("SELECT id, supplier_name FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")

    for part, _ in resolved_lines:
        if part["supplier_id"] != supplier_id:
            raise HTTPException(status_code=400, detail="All supplier order lines must belong to the selected supplier")

    now = utc_now_iso()
    estimated_arrival = payload.estimated_arrival
    if workflow_role_name(current_user) == "user" and parse_iso_datetime(estimated_arrival) is None:
        estimated_arrival = (datetime.utcnow() + timedelta(seconds=MANUAL_SUPPLIER_DELIVERY_SECONDS)).isoformat(timespec="seconds")
    estimated_arrival = estimated_arrival or "Pending confirmation"

    order_id = make_order_id("SO")
    while connection.execute("SELECT 1 FROM order_suppliers WHERE id = ?", (order_id,)).fetchone():
        order_id = make_order_id("SO")

    connection.execute(
        """
        INSERT INTO order_suppliers (
            id, supplier_id, supplier_name, user_id, location, status,
            estimated_arrival, postponed_until, received_at, stock_applied,
            notes, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, 'Pending', ?, NULL, NULL, 0, NULL, ?, ?)
        """,
        (
            order_id,
            supplier["id"],
            supplier["supplier_name"],
            current_user.get("id"),
            location,
            estimated_arrival,
            now,
            now,
        ),
    )

    for part, quantity in resolved_lines:
        connection.execute(
            """
            INSERT INTO order_supplier_lines (
                order_id, part_id, sku, part_name, quantity, received_quantity, unit_price
            )
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (order_id, part["part_id"], part["sku"], part["part_name"], quantity, part["unit_price"]),
        )

    connection.commit()
    return supplier_order_to_dict(connection, fetch_supplier_order(connection, order_id))


INCOMING_CLIENT_NAMES = (
    "RRParts Web Client",
    "Bucharest Auto Service",
    "Peugeot Fleet Desk",
    "Express Service Counter",
    "Local Fleet Client",
)


def workflow_role_name(current_user: dict) -> str:
    return current_user.get("role_name", current_user.get("role", "user"))


def user_order_location(current_user: dict) -> str:
    for key in ("company", "full_name", "username"):
        value = current_user.get(key)
        if value:
            return str(value)
    return "My Store"


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def order_stream_cutoff(connection: sqlite3.Connection, current_user: dict) -> str | None:
    if workflow_role_name(current_user) != "user" or not current_user.get("id"):
        return None

    ensure_order_workflow_schema(connection)
    user_id = int(current_user["id"])
    stream = connection.execute(
        "SELECT created_at FROM order_notification_stream WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if stream is not None:
        return stream["created_at"]

    now_iso = utc_now_iso()
    connection.execute(
        """
        INSERT INTO order_notification_stream (user_id, last_generated_at, next_kind, created_at, updated_at)
        VALUES (?, ?, 'client', ?, ?)
        """,
        (user_id, now_iso, now_iso, now_iso),
    )
    connection.commit()
    return now_iso


def active_incoming_order_count(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    stream_created_at: str | None,
) -> int:
    cutoff_clause = ""
    client_params: list[object] = [user_id]
    supplier_params: list[object] = [user_id]
    if stream_created_at:
        cutoff_clause = " AND created_at >= ?"
        client_params.append(stream_created_at)
        supplier_params.append(stream_created_at)

    client_count = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM order_clients
        WHERE user_id = ?
          AND status IN ('Pending', 'Scheduled')
          {cutoff_clause}
        """,
        client_params,
    ).fetchone()[0]
    supplier_count = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM order_suppliers
        WHERE user_id = ?
          AND (
              status IN ('Pending', 'Delayed')
              OR (status = 'Delivered' AND stock_applied = 0)
          )
          {cutoff_clause}
        """,
        supplier_params,
    ).fetchone()[0]
    return int(client_count or 0) + int(supplier_count or 0)


def random_catalog_part(connection: sqlite3.Connection, *, require_supplier: bool = False) -> sqlite3.Row | None:
    where_clause = "WHERE supplier_id IS NOT NULL" if require_supplier else ""
    return connection.execute(
        f"""
        SELECT id AS part_id, min_order_qty
        FROM parts
        {where_clause}
        ORDER BY random()
        LIMIT 1
        """
    ).fetchone()


def create_incoming_client_order(connection: sqlite3.Connection, current_user: dict) -> dict | None:
    part = random_catalog_part(connection)
    if part is None:
        return None

    quantity = random.randint(1, max(2, min(8, int(part["min_order_qty"] or 4))))
    payload = ClientOrderCreatePayload(
        client_name=random.choice(INCOMING_CLIENT_NAMES),
        location=user_order_location(current_user),
        requested_time=datetime.utcnow().strftime("%H:%M"),
        items=[WorkflowOrderLinePayload(part_id=part["part_id"], quantity=quantity)],
    )
    return create_client_order_record(connection, payload, current_user)


def create_incoming_supplier_delivery(connection: sqlite3.Connection, current_user: dict) -> dict | None:
    part = random_catalog_part(connection, require_supplier=True)
    if part is None:
        return None

    quantity = random.randint(10, max(20, min(80, int(part["min_order_qty"] or 20) * 4)))
    payload = SupplierOrderCreatePayload(
        location=user_order_location(current_user),
        estimated_arrival="Arrived now",
        items=[WorkflowOrderLinePayload(part_id=part["part_id"], quantity=quantity)],
    )
    created = create_supplier_order_record(connection, payload, current_user)
    now = utc_now_iso()
    connection.execute(
        """
        UPDATE order_suppliers
        SET status = 'Delivered',
            estimated_arrival = 'Arrived now',
            received_at = NULL,
            stock_applied = 0,
            updated_at = ?
        WHERE id = ?
        """,
        (now, created["id"]),
    )
    connection.commit()
    return supplier_order_to_dict(connection, fetch_supplier_order(connection, created["id"]))


def maybe_generate_incoming_order(
    connection: sqlite3.Connection,
    current_user: dict,
    *,
    interval_seconds: int = INCOMING_ORDER_INTERVAL_SECONDS,
) -> dict | None:
    if workflow_role_name(current_user) != "user" or not current_user.get("id"):
        return None

    ensure_order_workflow_schema(connection)
    user_id = int(current_user["id"])
    now = datetime.utcnow()
    now_iso = now.isoformat(timespec="seconds")
    stream = connection.execute(
        "SELECT user_id, last_generated_at, next_kind, created_at FROM order_notification_stream WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if stream is None:
        connection.execute(
            """
            INSERT INTO order_notification_stream (user_id, last_generated_at, next_kind, created_at, updated_at)
            VALUES (?, ?, 'client', ?, ?)
            """,
            (user_id, now_iso, now_iso, now_iso),
        )
        connection.commit()
        return None

    if active_incoming_order_count(
        connection,
        user_id=user_id,
        stream_created_at=stream["last_generated_at"] or stream["created_at"],
    ) >= MAX_ACTIVE_INCOMING_ORDERS:
        return None

    last_generated_at = parse_iso_datetime(stream["last_generated_at"])
    if last_generated_at and (now - last_generated_at).total_seconds() < interval_seconds:
        return None

    kind = stream["next_kind"] or "client"
    order = create_incoming_client_order(connection, current_user) if kind == "client" else create_incoming_supplier_delivery(connection, current_user)
    if order is None:
        return None

    next_kind = "supplier" if kind == "client" else "client"
    connection.execute(
        """
        UPDATE order_notification_stream
        SET last_generated_at = ?, next_kind = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (now_iso, next_kind, now_iso, user_id),
    )
    connection.commit()
    return {"kind": kind, "order_id": order["id"]}


def update_stock_quantity(
    connection: sqlite3.Connection,
    *,
    part_id: int,
    location: str,
    delta: int,
) -> None:
    stock = connection.execute(
        """
        SELECT current_stock
        FROM stock
        WHERE part_id = ? AND (location = ? OR location_id = ?)
        """,
        (part_id, location, location),
    ).fetchone()

    if stock is None:
        raise ValueError(f"Stock record not found for part {part_id} at {location}")

    current_stock = int(stock["current_stock"])
    next_stock = current_stock + delta
    if next_stock < 0:
        raise ValueError(f"Insufficient stock for part {part_id} at {location}")

    connection.execute(
        """
        UPDATE stock
        SET current_stock = ?, last_updated = ?
        WHERE part_id = ? AND (location = ? OR location_id = ?)
        """,
        (next_stock, utc_now_iso(), part_id, location, location),
    )


def line_to_frontend_shape(row: sqlite3.Row) -> dict:
    line = dict(row)
    allocated_quantity = line.get("allocated_quantity", 0)
    shortage_quantity = line.get("shortage_quantity", 0)
    received_quantity = line.get("received_quantity", 0)
    return {
        "id": line["id"],
        "productId": str(line["part_id"]),
        "part_id": line["part_id"],
        "sku": line["sku"],
        "name": line["part_name"],
        "part_name": line["part_name"],
        "quantity": line["quantity"],
        "allocatedQuantity": allocated_quantity,
        "allocated_quantity": allocated_quantity,
        "shortageQuantity": shortage_quantity,
        "shortage_quantity": shortage_quantity,
        "receivedQuantity": received_quantity,
        "received_quantity": received_quantity,
        "unitPrice": line["unit_price"],
        "unit_price": line["unit_price"],
        "line_total": round(line["quantity"] * line["unit_price"], 2),
    }


def client_order_to_dict(connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
    order = dict(row)
    lines = [
        line_to_frontend_shape(line)
        for line in connection.execute(
            "SELECT * FROM order_client_lines WHERE order_id = ? ORDER BY id",
            (order["id"],),
        ).fetchall()
    ]
    return {
        "id": order["id"],
        "client": order["client_name"],
        "client_name": order["client_name"],
        "user_id": order["user_id"],
        "location": order["location"],
        "items": lines,
        "requestedTime": order["requested_time"],
        "requested_time": order["requested_time"],
        "status": order["status"],
        "fulfillmentStatus": order.get("fulfillment_status", "unreviewed"),
        "fulfillment_status": order.get("fulfillment_status", "unreviewed"),
        "createdAt": order["created_at"],
        "created_at": order["created_at"],
        "scheduledFor": order["scheduled_for"],
        "scheduled_for": order["scheduled_for"],
        "stockApplied": bool(order["stock_applied"]),
        "stock_applied": bool(order["stock_applied"]),
        "shortageQuantity": order.get("shortage_quantity", 0),
        "shortage_quantity": order.get("shortage_quantity", 0),
        "notes": order.get("notes"),
        "total_quantity": sum(line["quantity"] for line in lines),
        "total_value": round(sum(line["line_total"] for line in lines), 2),
    }


def supplier_order_to_dict(connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
    order = dict(row)
    lines = [
        line_to_frontend_shape(line)
        for line in connection.execute(
            "SELECT * FROM order_supplier_lines WHERE order_id = ? ORDER BY id",
            (order["id"],),
        ).fetchall()
    ]
    return {
        "id": order["id"],
        "supplier": order["supplier_name"],
        "supplier_id": order["supplier_id"],
        "supplier_name": order["supplier_name"],
        "user_id": order["user_id"],
        "location": order["location"],
        "items": lines,
        "status": order["status"],
        "createdAt": order["created_at"],
        "created_at": order["created_at"],
        "estimatedArrival": order["estimated_arrival"],
        "estimated_arrival": order["estimated_arrival"],
        "postponedUntil": order["postponed_until"],
        "postponed_until": order["postponed_until"],
        "receivedAt": order["received_at"],
        "received_at": order["received_at"],
        "sourceClientOrderId": order.get("source_client_order_id"),
        "source_client_order_id": order.get("source_client_order_id"),
        "stockApplied": bool(order["stock_applied"]),
        "stock_applied": bool(order["stock_applied"]),
        "notes": order.get("notes"),
        "total_quantity": sum(line["quantity"] for line in lines),
        "total_value": round(sum(line["line_total"] for line in lines), 2),
    }


def release_due_supplier_orders(connection: sqlite3.Connection, current_user: dict | None = None) -> int:
    ensure_order_workflow_schema(connection)
    params: list[object] = []
    scope_clause = ""
    if current_user and workflow_role_name(current_user) == "user" and current_user.get("id"):
        scope_clause = " AND user_id = ?"
        params.append(current_user["id"])

    rows = connection.execute(
        f"""
        SELECT id, user_id, status, estimated_arrival, postponed_until, created_at
        FROM order_suppliers
        WHERE status IN ('Pending', 'Delayed')
          AND stock_applied = 0
          {scope_clause}
        """,
        params,
    ).fetchall()

    now = datetime.utcnow()
    now_iso = now.isoformat(timespec="seconds")
    released = 0
    for row in rows:
        due_value = row["postponed_until"] if row["status"] == "Delayed" else row["estimated_arrival"]
        due_at = parse_iso_datetime(due_value)
        if due_at is None and row["status"] == "Pending" and row["user_id"] is not None:
            created_at = parse_iso_datetime(row["created_at"])
            if created_at is not None:
                due_at = created_at + timedelta(seconds=MANUAL_SUPPLIER_DELIVERY_SECONDS)
        if due_at is None or due_at > now:
            continue
        connection.execute(
            """
            UPDATE order_suppliers
            SET status = 'Delivered',
                estimated_arrival = 'Arrived now',
                received_at = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (now_iso, row["id"]),
        )
        released += 1

    if released:
        connection.commit()
    return released


def create_supplier_replenishments_for_client_shortage(
    connection: sqlite3.Connection,
    client_order_id: str,
) -> list[str]:
    client_order = fetch_client_order(connection, client_order_id)
    if int(client_order["shortage_quantity"] or 0) <= 0:
        return []

    existing = connection.execute(
        "SELECT id FROM order_suppliers WHERE source_client_order_id = ? LIMIT 1",
        (client_order_id,),
    ).fetchone()
    if existing is not None:
        return []

    rows = connection.execute(
        """
        SELECT
            l.part_id,
            l.sku,
            l.part_name,
            l.shortage_quantity,
            l.unit_price,
            p.supplier_id,
            COALESCE(s.supplier_name, p.supplier_id, 'Unknown Supplier') AS supplier_name
        FROM order_client_lines l
        JOIN parts p ON p.id = l.part_id
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        WHERE l.order_id = ?
          AND l.shortage_quantity > 0
        ORDER BY p.supplier_id, l.id
        """,
        (client_order_id,),
    ).fetchall()
    if not rows:
        return []

    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        supplier_key = row["supplier_id"] or "UNKNOWN"
        grouped.setdefault(supplier_key, []).append(row)

    created_order_ids: list[str] = []
    now_iso = utc_now_iso()
    for supplier_id, supplier_rows in grouped.items():
        order_id = make_order_id("SO")
        while connection.execute("SELECT 1 FROM order_suppliers WHERE id = ?", (order_id,)).fetchone():
            order_id = make_order_id("SO")

        arrival_at = (datetime.utcnow() + timedelta(seconds=MANUAL_SUPPLIER_DELIVERY_SECONDS)).isoformat(timespec="seconds")
        supplier_name = supplier_rows[0]["supplier_name"] or supplier_id
        connection.execute(
            """
            INSERT INTO order_suppliers (
                id, supplier_id, supplier_name, user_id, location, status,
                estimated_arrival, postponed_until, received_at, source_client_order_id,
                stock_applied, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'Pending', ?, NULL, NULL, ?, 0, ?, ?, ?)
            """,
            (
                order_id,
                None if supplier_id == "UNKNOWN" else supplier_id,
                supplier_name,
                client_order["user_id"],
                client_order["location"],
                arrival_at,
                client_order_id,
                f"Auto-created replenishment for client backorder {client_order_id}.",
                now_iso,
                now_iso,
            ),
        )

        for row in supplier_rows:
            connection.execute(
                """
                INSERT INTO order_supplier_lines (
                    order_id, part_id, sku, part_name, quantity, received_quantity, unit_price
                )
                VALUES (?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    order_id,
                    row["part_id"],
                    row["sku"],
                    row["part_name"],
                    int(row["shortage_quantity"] or 0),
                    row["unit_price"],
                ),
            )
        created_order_ids.append(order_id)

    return created_order_ids


def fulfill_client_backorder_from_available_stock(connection: sqlite3.Connection, client_order_id: str | None) -> None:
    if not client_order_id:
        return

    order = connection.execute(
        """
        SELECT id, user_id, location, status, stock_applied, shortage_quantity
        FROM order_clients
        WHERE id = ?
        """,
        (client_order_id,),
    ).fetchone()
    if order is None or int(order["shortage_quantity"] or 0) <= 0:
        return

    lines = connection.execute(
        """
        SELECT id, part_id, shortage_quantity
        FROM order_client_lines
        WHERE order_id = ?
          AND shortage_quantity > 0
        ORDER BY id
        """,
        (client_order_id,),
    ).fetchall()

    for line in lines:
        missing = int(line["shortage_quantity"] or 0)
        if missing <= 0:
            continue

        if order["user_id"] is None:
            stock = connection.execute(
                """
                SELECT current_stock
                FROM stock
                WHERE part_id = ? AND (location = ? OR location_id = ?)
                """,
                (line["part_id"], order["location"], order["location"]),
            ).fetchone()
        else:
            stock = connection.execute(
                """
                SELECT current_stock
                FROM user_stock
                WHERE user_id = ? AND part_id = ?
                """,
                (order["user_id"], line["part_id"]),
            ).fetchone()

        available = int(stock["current_stock"]) if stock is not None else 0
        allocated = min(available, missing)
        if allocated <= 0:
            continue

        if order["user_id"] is None:
            update_stock_quantity(
                connection,
                part_id=line["part_id"],
                location=order["location"],
                delta=-allocated,
            )
        else:
            change_user_stock_quantity(
                connection,
                user_id=order["user_id"],
                part_id=line["part_id"],
                location=order["location"],
                delta=-allocated,
            )

        connection.execute(
            """
            UPDATE order_client_lines
            SET allocated_quantity = allocated_quantity + ?,
                shortage_quantity = shortage_quantity - ?
            WHERE id = ?
            """,
            (allocated, allocated, line["id"]),
        )

    totals = connection.execute(
        """
        SELECT
            COALESCE(SUM(quantity), 0) AS requested,
            COALESCE(SUM(allocated_quantity), 0) AS allocated,
            COALESCE(SUM(shortage_quantity), 0) AS shortage
        FROM order_client_lines
        WHERE order_id = ?
        """,
        (client_order_id,),
    ).fetchone()
    total_allocated = int(totals["allocated"] or 0)
    total_shortage = int(totals["shortage"] or 0)

    if total_shortage == 0:
        fulfillment_status = "ready"
        next_status = "Approved"
    elif total_allocated == 0:
        fulfillment_status = "backorder"
        next_status = "Approved"
    else:
        fulfillment_status = "partial"
        next_status = "Approved"

    connection.execute(
        """
        UPDATE order_clients
        SET status = ?,
            fulfillment_status = ?,
            shortage_quantity = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (next_status, fulfillment_status, total_shortage, utc_now_iso(), client_order_id),
    )


def apply_client_order_stock(connection: sqlite3.Connection, order_id: str) -> None:
    ensure_user_stock_schema(connection)
    order = connection.execute(
        "SELECT id, user_id, location, stock_applied FROM order_clients WHERE id = ?",
        (order_id,),
    ).fetchone()
    if order is None:
        raise ValueError("Client order not found")
    if order["stock_applied"]:
        return

    lines = connection.execute(
        "SELECT id, part_id, quantity FROM order_client_lines WHERE order_id = ?",
        (order_id,),
    ).fetchall()
    total_requested = 0
    total_allocated = 0
    total_shortage = 0

    for line in lines:
        requested_quantity = int(line["quantity"])
        if order["user_id"] is None:
            stock = connection.execute(
                """
                SELECT current_stock
                FROM stock
                WHERE part_id = ? AND (location = ? OR location_id = ?)
                """,
                (line["part_id"], order["location"], order["location"]),
            ).fetchone()
        else:
            stock = connection.execute(
                """
                SELECT current_stock
                FROM user_stock
                WHERE user_id = ? AND part_id = ?
                """,
                (order["user_id"], line["part_id"]),
            ).fetchone()
        available_quantity = int(stock["current_stock"]) if stock is not None else 0
        allocated_quantity = min(available_quantity, requested_quantity)
        shortage_quantity = requested_quantity - allocated_quantity

        if allocated_quantity > 0:
            if order["user_id"] is None:
                update_stock_quantity(
                    connection,
                    part_id=line["part_id"],
                    location=order["location"],
                    delta=-allocated_quantity,
                )
            else:
                change_user_stock_quantity(
                    connection,
                    user_id=order["user_id"],
                    part_id=line["part_id"],
                    location=order["location"],
                    delta=-allocated_quantity,
                )

        connection.execute(
            """
            UPDATE order_client_lines
            SET allocated_quantity = ?, shortage_quantity = ?
            WHERE id = ?
            """,
            (allocated_quantity, shortage_quantity, line["id"]),
        )
        total_requested += requested_quantity
        total_allocated += allocated_quantity
        total_shortage += shortage_quantity

    if total_shortage == 0:
        fulfillment_status = "ready"
    elif total_allocated == 0 and total_requested > 0:
        fulfillment_status = "backorder"
    else:
        fulfillment_status = "partial"

    connection.execute(
        """
        UPDATE order_clients
        SET stock_applied = 1,
            fulfillment_status = ?,
            shortage_quantity = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (fulfillment_status, total_shortage, utc_now_iso(), order_id),
    )


def record_client_order_sales(connection: sqlite3.Connection, order_id: str) -> int:
    ensure_order_workflow_schema(connection)
    order = connection.execute(
        """
        SELECT id, user_id, location
        FROM order_clients
        WHERE id = ?
        """,
        (order_id,),
    ).fetchone()
    if order is None:
        raise ValueError("Client order not found")

    rows = connection.execute(
        """
        SELECT
            l.id AS line_id,
            l.part_id,
            l.sku,
            l.part_name,
            l.quantity,
            l.allocated_quantity,
            l.unit_price,
            p.category
        FROM order_client_lines l
        JOIN parts p ON p.id = l.part_id
        WHERE l.order_id = ?
        ORDER BY l.id
        """,
        (order_id,),
    ).fetchall()

    now_iso = datetime.now().astimezone().isoformat(timespec="seconds")
    inserted = 0
    for row in rows:
        quantity = int(row["allocated_quantity"] or row["quantity"] or 0)
        if quantity <= 0:
            continue

        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO order_sales_events (
                order_client_id, order_client_line_id, user_id, part_id, sku,
                part_name, category, location, quantity_sold, unit_price,
                revenue_eur, sold_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order["id"],
                row["line_id"],
                order["user_id"],
                row["part_id"],
                row["sku"],
                row["part_name"],
                row["category"],
                order["location"],
                quantity,
                float(row["unit_price"] or 0),
                round(quantity * float(row["unit_price"] or 0), 2),
                now_iso,
                now_iso,
            ),
        )
        inserted += cursor.rowcount

    return inserted


def apply_supplier_order_stock(connection: sqlite3.Connection, order_id: str) -> None:
    ensure_user_stock_schema(connection)
    order = connection.execute(
        "SELECT id, user_id, location, stock_applied, source_client_order_id FROM order_suppliers WHERE id = ?",
        (order_id,),
    ).fetchone()
    if order is None:
        raise ValueError("Supplier order not found")
    if order["stock_applied"]:
        return

    lines = connection.execute(
        "SELECT id, part_id, quantity FROM order_supplier_lines WHERE order_id = ?",
        (order_id,),
    ).fetchall()
    for line in lines:
        if order["user_id"] is None:
            update_stock_quantity(
                connection,
                part_id=line["part_id"],
                location=order["location"],
                delta=int(line["quantity"]),
            )
        else:
            change_user_stock_quantity(
                connection,
                user_id=order["user_id"],
                part_id=line["part_id"],
                location=order["location"],
                delta=int(line["quantity"]),
            )
        connection.execute(
            "UPDATE order_supplier_lines SET received_quantity = ? WHERE id = ?",
            (int(line["quantity"]), line["id"]),
        )

    now = utc_now_iso()
    connection.execute(
        """
        UPDATE order_suppliers
        SET status = 'Received', stock_applied = 1, received_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (now, now, order_id),
    )
    fulfill_client_backorder_from_available_stock(connection, order["source_client_order_id"])


DEMO_CLIENT_ORDERS = [
    {
        "id": "CL-4821",
        "client_name": "Andrei Popescu",
        "location": "PL_WAW",
        "requested_time": "14:30",
        "status": "Pending",
        "fulfillment_status": "unreviewed",
        "scheduled_for": None,
        "notes": "Walk-in customer order awaiting approval.",
        "items": [("PEU-BRAKE-PADS-F", 3)],
    },
    {
        "id": "CL-4822",
        "client_name": "Mara Service Auto",
        "location": "ES_MAD",
        "requested_time": "16:00",
        "status": "Pending",
        "fulfillment_status": "unreviewed",
        "scheduled_for": None,
        "notes": "Service garage order for same-day pickup.",
        "items": [("PEU-WIPER-650", 8)],
    },
    {
        "id": "CL-4815",
        "client_name": "Ionescu Fleet",
        "location": "RO_BUC",
        "requested_time": "11:45",
        "status": "Approved",
        "fulfillment_status": "ready",
        "scheduled_for": None,
        "notes": "Fleet maintenance order, stock should be reserved immediately.",
        "items": [("PEU-OIL-FILTER", 12)],
        "apply_stock": True,
    },
    {
        "id": "CL-4830",
        "client_name": "Nordic Lease Group",
        "location": "FI_HEL",
        "requested_time": "09:10",
        "status": "Scheduled",
        "fulfillment_status": "ready",
        "scheduled_for": (datetime.utcnow() + timedelta(days=1, hours=2)).isoformat(timespec="seconds"),
        "notes": "Scheduled tire pickup for tomorrow morning.",
        "items": [("PEU-WINTER-TIRE-205", 40)],
    },
    {
        "id": "CL-4831",
        "client_name": "Helsinki Fleet Desk",
        "location": "FI_HEL",
        "requested_time": "10:20",
        "status": "Approved",
        "fulfillment_status": "ready",
        "scheduled_for": None,
        "notes": "Accepted large tire order; local stock is intentionally not enough.",
        "items": [("PEU-WINTER-TIRE-205", 170)],
        "apply_stock": True,
    },
    {
        "id": "CL-4832",
        "client_name": "Copenhagen Retail",
        "location": "DK_CPH",
        "requested_time": "13:05",
        "status": "Denied",
        "fulfillment_status": "denied",
        "scheduled_for": None,
        "notes": "Denied by manager after duplicate request.",
        "items": [("PEU-RUBBER-MATS", 20)],
    },
    {
        "id": "CL-4833",
        "client_name": "Berlin Workshop",
        "location": "DE_BER",
        "requested_time": "15:15",
        "status": "Delivered",
        "fulfillment_status": "ready",
        "scheduled_for": None,
        "notes": "Delivered client order, stock already allocated.",
        "items": [("PEU-ADBLUE-10L", 25)],
        "apply_stock": True,
    },
    {
        "id": "CL-4834",
        "client_name": "Amsterdam Garage",
        "location": "NL_AMS",
        "requested_time": "12:35",
        "status": "Pending",
        "fulfillment_status": "unreviewed",
        "scheduled_for": None,
        "notes": "Mixed electrical parts request.",
        "items": [("PEU-BATT-70AH", 6), ("PEU-HEADLIGHT-H7", 12)],
    },
    {
        "id": "CL-4835",
        "client_name": "Tallinn Emergency Fleet",
        "location": "EE_TLL",
        "requested_time": "17:20",
        "status": "Approved",
        "fulfillment_status": "ready",
        "scheduled_for": None,
        "notes": "Accepted oversized battery order to demonstrate backorder handling.",
        "items": [("PEU-BATT-70AH", 200)],
        "apply_stock": True,
    },
]

DEMO_SUPPLIER_ORDERS = [
    {
        "id": "SO-1048",
        "location": "ES_MAD",
        "status": "Delivered",
        "estimated_arrival": "Arrived today",
        "postponed_until": None,
        "received_at": None,
        "stock_applied": False,
        "notes": "Delivered by supplier, waiting for warehouse receiving.",
        "items": [("PEU-WINTER-TIRE-205", 35)],
    },
    {
        "id": "SO-1049",
        "location": "PL_WAW",
        "status": "Approved",
        "estimated_arrival": "3 days",
        "postponed_until": None,
        "received_at": None,
        "stock_applied": False,
        "notes": "Approved replenishment for brake stock.",
        "items": [("PEU-BRAKE-PADS-F", 50)],
    },
    {
        "id": "SO-1050",
        "location": "DK_CPH",
        "status": "Delayed",
        "estimated_arrival": "9 days",
        "postponed_until": (datetime.utcnow() + timedelta(days=9)).isoformat(timespec="seconds"),
        "received_at": None,
        "stock_applied": False,
        "notes": "Supplier reported transport delay.",
        "items": [("PEU-CABIN-CARBON", 80)],
    },
    {
        "id": "SO-1060",
        "location": "DE_BER",
        "status": "Pending",
        "estimated_arrival": "Pending confirmation",
        "postponed_until": None,
        "received_at": None,
        "stock_applied": False,
        "notes": "Electrical parts order awaiting supplier confirmation.",
        "items": [("PEU-BATT-70AH", 45), ("PEU-HEADLIGHT-H7", 120)],
    },
    {
        "id": "SO-1061",
        "location": "RO_BUC",
        "status": "Delivered",
        "estimated_arrival": "Received today",
        "postponed_until": None,
        "received_at": datetime.utcnow().isoformat(timespec="seconds"),
        "stock_applied": True,
        "notes": "Received replenishment, stock should already be increased.",
        "items": [("PEU-OIL-FILTER", 100)],
    },
    {
        "id": "SO-1062",
        "location": "FR_PAR",
        "status": "Refused",
        "estimated_arrival": "Refused at dock",
        "postponed_until": None,
        "received_at": None,
        "stock_applied": False,
        "notes": "Refused because packaging was damaged.",
        "items": [("PEU-COOLANT-PREMIX", 60)],
    },
    {
        "id": "SO-1063",
        "location": "SE_STO",
        "status": "Pending",
        "estimated_arrival": "5 days",
        "postponed_until": None,
        "received_at": None,
        "stock_applied": False,
        "notes": "Fluids replenishment for northern locations.",
        "items": [("PEU-WF-WINTER-5L", 120), ("PEU-ADBLUE-10L", 90)],
    },
    {
        "id": "SO-1064",
        "location": "FI_HEL",
        "status": "Approved",
        "estimated_arrival": "6 days",
        "postponed_until": None,
        "received_at": None,
        "stock_applied": False,
        "notes": "Accessory replenishment after strong regional demand.",
        "items": [("PEU-WIPER-650", 70), ("PEU-RUBBER-MATS", 40)],
    },
]


def _insert_client_demo_order(connection: sqlite3.Connection, order: dict, now_iso: str) -> None:
    connection.execute("DELETE FROM order_clients WHERE id = ?", (order["id"],))
    connection.execute(
        """
        INSERT INTO order_clients (
            id, client_name, user_id, location, requested_time, status,
            fulfillment_status, scheduled_for, stock_applied, shortage_quantity,
            notes, created_at, updated_at
        )
        VALUES (?, ?, NULL, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?)
        """,
        (
            order["id"],
            order["client_name"],
            order["location"],
            order["requested_time"],
            order["status"],
            order["fulfillment_status"],
            order["scheduled_for"],
            order["notes"],
            now_iso,
            now_iso,
        ),
    )

    for sku, quantity in order["items"]:
        part = get_part_for_order(connection, sku=sku, location=order["location"])
        if part is None:
            continue
        connection.execute(
            """
            INSERT INTO order_client_lines (
                order_id, part_id, sku, part_name, quantity,
                allocated_quantity, shortage_quantity, unit_price
            )
            VALUES (?, ?, ?, ?, ?, 0, 0, ?)
            """,
            (order["id"], part["part_id"], part["sku"], part["part_name"], quantity, part["unit_price"]),
        )

    if order.get("apply_stock"):
        apply_client_order_stock(connection, order["id"])

    if order["status"] == "Denied":
        connection.execute(
            """
            UPDATE order_clients
            SET fulfillment_status = 'denied', updated_at = ?
            WHERE id = ?
            """,
            (utc_now_iso(), order["id"]),
        )


def _insert_supplier_demo_order(connection: sqlite3.Connection, order: dict, now_iso: str) -> None:
    connection.execute("DELETE FROM order_suppliers WHERE id = ?", (order["id"],))

    first_part = get_part_for_order(connection, sku=order["items"][0][0], location=order["location"])
    if first_part is None:
        return

    connection.execute(
        """
        INSERT INTO order_suppliers (
            id, supplier_id, supplier_name, user_id, location, status,
            estimated_arrival, postponed_until, received_at, stock_applied,
            notes, created_at, updated_at
        )
        VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, 0, ?, ?, ?)
        """,
        (
            order["id"],
            first_part["supplier_id"],
            first_part["supplier_name"] or "Unknown Supplier",
            order["location"],
            order["status"],
            order["estimated_arrival"],
            order["postponed_until"],
            order["received_at"],
            order["notes"],
            now_iso,
            now_iso,
        ),
    )

    for sku, quantity in order["items"]:
        part = get_part_for_order(connection, sku=sku, location=order["location"])
        if part is None:
            continue
        if part["supplier_id"] != first_part["supplier_id"]:
            continue
        connection.execute(
            """
            INSERT INTO order_supplier_lines (
                order_id, part_id, sku, part_name, quantity, received_quantity, unit_price
            )
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (order["id"], part["part_id"], part["sku"], part["part_name"], quantity, part["unit_price"]),
        )

    if order.get("stock_applied"):
        apply_supplier_order_stock(connection, order["id"])


def replace_demo_order_workflows(connection: sqlite3.Connection) -> None:
    ensure_order_workflow_schema(connection)
    now_iso = datetime.utcnow().isoformat(timespec="seconds")

    for order in DEMO_CLIENT_ORDERS:
        _insert_client_demo_order(connection, order, now_iso)

    for order in DEMO_SUPPLIER_ORDERS:
        _insert_supplier_demo_order(connection, order, now_iso)

    connection.commit()


def seed_demo_order_workflows(connection: sqlite3.Connection, replace_existing: bool = False) -> None:
    ensure_order_workflow_schema(connection)

    if replace_existing:
        replace_demo_order_workflows(connection)
        return

    has_clients = connection.execute("SELECT 1 FROM order_clients LIMIT 1").fetchone()
    has_suppliers = connection.execute("SELECT 1 FROM order_suppliers LIMIT 1").fetchone()
    if has_clients or has_suppliers:
        return

    replace_demo_order_workflows(connection)
