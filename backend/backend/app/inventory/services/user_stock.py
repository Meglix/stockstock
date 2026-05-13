from __future__ import annotations

from datetime import datetime
import sqlite3

from fastapi import HTTPException

from app.inventory.services.stock_status import stock_health


USER_STOCK_DDL = """
CREATE TABLE IF NOT EXISTS user_stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    part_id INTEGER NOT NULL,
    location TEXT NOT NULL DEFAULT 'My Store',
    location_id TEXT,
    current_stock INTEGER NOT NULL DEFAULT 0 CHECK (current_stock >= 0),
    reorder_point INTEGER NOT NULL DEFAULT 0 CHECK (reorder_point >= 0),
    safety_stock INTEGER NOT NULL DEFAULT 0 CHECK (safety_stock >= 0),
    optimal_stock INTEGER NOT NULL DEFAULT 1 CHECK (optimal_stock >= safety_stock),
    min_order_qty INTEGER,
    lead_time_days INTEGER,
    pending_order_qty INTEGER NOT NULL DEFAULT 0 CHECK (pending_order_qty >= 0),
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, part_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_stock_user ON user_stock(user_id);
CREATE INDEX IF NOT EXISTS idx_user_stock_part ON user_stock(part_id);
"""


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def role_name(current_user: dict) -> str:
    return current_user.get("role_name", current_user.get("role", "user"))


def is_user(current_user: dict) -> bool:
    return role_name(current_user) == "user"


def ensure_user_stock_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(USER_STOCK_DDL)


def default_store_location(current_user: dict | None = None, fallback: str | None = None) -> str:
    if fallback:
        return fallback
    if current_user:
        for key in ("company", "full_name", "username"):
            value = current_user.get(key)
            if value:
                return str(value)
    return "My Store"


def display_category(category: str | None) -> str:
    if not category:
        return "Uncategorized"
    words = category.replace("_", " ").replace("-", " ").split()
    return " ".join(word.upper() if len(word) <= 2 else word.capitalize() for word in words)


def resolve_catalog_part(
    connection: sqlite3.Connection,
    *,
    part_id: int | None = None,
    sku: str | None = None,
) -> sqlite3.Row:
    filters = []
    params: list[object] = []
    if part_id is not None:
        filters.append("p.id = ?")
        params.append(part_id)
    if sku:
        filters.append("p.sku = ?")
        params.append(sku.strip().upper())

    if not filters:
        raise HTTPException(status_code=422, detail="part_id or sku is required")

    row = connection.execute(
        f"""
        SELECT
            p.id AS part_id,
            p.sku,
            p.part_name,
            p.category,
            p.supplier_id,
            p.unit_price,
            p.min_order_qty,
            p.lead_time_days,
            s.supplier_name
        FROM parts p
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        WHERE {' OR '.join(filters)}
        LIMIT 1
        """,
        params,
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Part not found in catalog")
    return row


def stock_row_to_api(row: sqlite3.Row) -> dict:
    current_stock = int(row["current_stock"] or 0)
    reorder_point = int(row["reorder_point"] or 0)
    optimal_stock = int(row["optimal_stock"] or 0)
    location = row["location"] or "My Store"
    return {
        "id": f"user-stock-{row['user_id']}-{row['part_id']}",
        "user_stock_id": row["id"],
        "user_id": row["user_id"],
        "productId": str(row["part_id"]),
        "product_id": str(row["part_id"]),
        "part_id": row["part_id"],
        "name": row["part_name"],
        "part_name": row["part_name"],
        "sku": row["sku"],
        "category": display_category(row["category"]),
        "raw_category": row["category"],
        "supplier": row["supplier_name"] or row["supplier_id"] or "Unknown Supplier",
        "supplier_id": row["supplier_id"],
        "current": current_stock,
        "current_stock": current_stock,
        "recommended": optimal_stock,
        "optimal_stock": optimal_stock,
        "reorderPoint": reorder_point,
        "reorder_point": reorder_point,
        "safety_stock": int(row["safety_stock"] or 0),
        "min_order_qty": int(row["min_order_qty"] or 0),
        "lead_time_days": int(row["lead_time_days"] or 0),
        "pending_order_qty": int(row["pending_order_qty"] or 0),
        "status": stock_health(current_stock, optimal_stock, reorder_point),
        "location": location,
        "location_id": row["location_id"],
        "last_updated": row["updated_at"],
        "updated_at": row["updated_at"],
    }


def user_stock_query() -> str:
    return """
    SELECT
        us.id,
        us.user_id,
        us.part_id,
        us.location,
        us.location_id,
        us.current_stock,
        us.reorder_point,
        us.safety_stock,
        us.optimal_stock,
        us.min_order_qty,
        us.lead_time_days,
        us.pending_order_qty,
        us.notes,
        us.created_at,
        us.updated_at,
        p.sku,
        p.part_name,
        p.category,
        p.supplier_id,
        s.supplier_name
    FROM user_stock us
    JOIN parts p ON p.id = us.part_id
    LEFT JOIN suppliers s ON s.id = p.supplier_id
    """


def list_user_stock(connection: sqlite3.Connection, current_user: dict) -> list[dict]:
    ensure_user_stock_schema(connection)
    rows = connection.execute(
        f"{user_stock_query()} WHERE us.user_id = ? ORDER BY p.part_name, p.sku",
        (current_user["id"],),
    ).fetchall()
    return [stock_row_to_api(row) for row in rows]


def get_user_stock_item(
    connection: sqlite3.Connection,
    current_user: dict,
    part_id: int,
) -> dict | None:
    ensure_user_stock_schema(connection)
    row = connection.execute(
        f"{user_stock_query()} WHERE us.user_id = ? AND us.part_id = ?",
        (current_user["id"], part_id),
    ).fetchone()
    return stock_row_to_api(row) if row else None


def get_user_stock_rows_for_parts(
    connection: sqlite3.Connection,
    current_user: dict,
    part_ids: list[int],
) -> dict[int, list[sqlite3.Row]]:
    ensure_user_stock_schema(connection)
    if not part_ids:
        return {}

    placeholders = ", ".join(["?"] * len(part_ids))
    rows = connection.execute(
        f"""
        SELECT
            us.part_id,
            us.location,
            us.location_id,
            NULL AS city,
            NULL AS country_code,
            us.current_stock,
            us.reorder_point,
            us.safety_stock,
            us.optimal_stock,
            us.min_order_qty,
            us.lead_time_days,
            us.pending_order_qty,
            us.updated_at AS last_updated
        FROM user_stock us
        WHERE us.user_id = ?
          AND us.part_id IN ({placeholders})
        ORDER BY us.part_id, us.current_stock ASC
        """,
        [current_user["id"], *part_ids],
    ).fetchall()

    by_part: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        by_part.setdefault(row["part_id"], []).append(row)
    return by_part


def payload_value(payload: object, name: str, default=None):
    value = getattr(payload, name, default)
    return default if value is None else value


def upsert_user_stock(connection: sqlite3.Connection, current_user: dict, payload: object) -> dict:
    ensure_user_stock_schema(connection)
    part = resolve_catalog_part(
        connection,
        part_id=getattr(payload, "part_id", None),
        sku=getattr(payload, "sku", None),
    )
    now = utc_now_iso()
    current_stock = int(payload_value(payload, "current_stock", 0))
    reorder_point = int(payload_value(payload, "reorder_point", 0))
    safety_stock = int(payload_value(payload, "safety_stock", 0))
    optimal_stock = int(payload_value(payload, "optimal_stock", max(current_stock, reorder_point, 1)))
    optimal_stock = max(optimal_stock, safety_stock, reorder_point, 1)
    location = default_store_location(current_user, getattr(payload, "location", None))

    connection.execute(
        """
        INSERT INTO user_stock (
            user_id, part_id, location, location_id, current_stock,
            reorder_point, safety_stock, optimal_stock, min_order_qty,
            lead_time_days, pending_order_qty, notes, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, part_id) DO UPDATE SET
            location = excluded.location,
            location_id = excluded.location_id,
            current_stock = excluded.current_stock,
            reorder_point = excluded.reorder_point,
            safety_stock = excluded.safety_stock,
            optimal_stock = excluded.optimal_stock,
            min_order_qty = excluded.min_order_qty,
            lead_time_days = excluded.lead_time_days,
            pending_order_qty = excluded.pending_order_qty,
            notes = excluded.notes,
            updated_at = excluded.updated_at
        """,
        (
            current_user["id"],
            part["part_id"],
            location,
            getattr(payload, "location_id", None),
            current_stock,
            reorder_point,
            safety_stock,
            optimal_stock,
            payload_value(payload, "min_order_qty", part["min_order_qty"] or 0),
            payload_value(payload, "lead_time_days", part["lead_time_days"] or 0),
            int(payload_value(payload, "pending_order_qty", 0)),
            getattr(payload, "notes", None),
            now,
            now,
        ),
    )
    connection.commit()
    item = get_user_stock_item(connection, current_user, part["part_id"])
    if item is None:
        raise HTTPException(status_code=500, detail="User stock record was not saved")
    return item


def patch_user_stock(
    connection: sqlite3.Connection,
    current_user: dict,
    part_id: int,
    payload: object,
) -> dict:
    ensure_user_stock_schema(connection)
    if get_user_stock_item(connection, current_user, part_id) is None:
        raise HTTPException(status_code=404, detail="User stock record not found")

    updates = []
    values: list[object] = []
    field_map = {
        "location": "location",
        "location_id": "location_id",
        "current_stock": "current_stock",
        "reorder_point": "reorder_point",
        "safety_stock": "safety_stock",
        "optimal_stock": "optimal_stock",
        "min_order_qty": "min_order_qty",
        "lead_time_days": "lead_time_days",
        "pending_order_qty": "pending_order_qty",
        "notes": "notes",
    }

    fields_set = getattr(payload, "model_fields_set", set(field_map))
    for payload_name, column_name in field_map.items():
        if payload_name not in fields_set:
            continue
        value = getattr(payload, payload_name, None)
        if value is None:
            continue
        updates.append(f"{column_name} = ?")
        values.append(value)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = ?")
    values.extend([utc_now_iso(), current_user["id"], part_id])
    connection.execute(
        f"UPDATE user_stock SET {', '.join(updates)} WHERE user_id = ? AND part_id = ?",
        values,
    )
    connection.commit()
    item = get_user_stock_item(connection, current_user, part_id)
    if item is None:
        raise HTTPException(status_code=404, detail="User stock record not found")
    return item


def delete_user_stock(connection: sqlite3.Connection, current_user: dict, part_id: int) -> None:
    ensure_user_stock_schema(connection)
    cursor = connection.execute(
        "DELETE FROM user_stock WHERE user_id = ? AND part_id = ?",
        (current_user["id"], part_id),
    )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="User stock record not found")
    connection.commit()


def change_user_stock_quantity(
    connection: sqlite3.Connection,
    *,
    user_id: int | None,
    part_id: int,
    delta: int,
    location: str | None = None,
) -> None:
    ensure_user_stock_schema(connection)
    if user_id is None:
        raise ValueError("User stock update requires a user_id")

    existing = connection.execute(
        "SELECT current_stock FROM user_stock WHERE user_id = ? AND part_id = ?",
        (user_id, part_id),
    ).fetchone()

    if existing is None:
        if delta < 0:
            raise ValueError(f"Insufficient user stock for part {part_id}")
        part = resolve_catalog_part(connection, part_id=part_id)
        now = utc_now_iso()
        connection.execute(
            """
            INSERT INTO user_stock (
                user_id, part_id, location, current_stock, reorder_point,
                safety_stock, optimal_stock, min_order_qty, lead_time_days,
                pending_order_qty, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 0, 0, ?, ?, ?, 0, ?, ?)
            """,
            (
                user_id,
                part_id,
                default_store_location(None, location),
                delta,
                max(delta, int(part["min_order_qty"] or 1), 1),
                int(part["min_order_qty"] or 0),
                int(part["lead_time_days"] or 0),
                now,
                now,
            ),
        )
        return

    next_stock = int(existing["current_stock"]) + delta
    if next_stock < 0:
        raise ValueError(f"Insufficient user stock for part {part_id}")

    connection.execute(
        """
        UPDATE user_stock
        SET current_stock = ?, updated_at = ?
        WHERE user_id = ? AND part_id = ?
        """,
        (next_stock, utc_now_iso(), user_id, part_id),
    )
