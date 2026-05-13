from __future__ import annotations

import sqlite3

from app.inventory.services.stock_status import catalog_stock_status
from app.inventory.services.user_stock import (
    ensure_user_stock_schema,
    get_user_stock_rows_for_parts,
)


def role_name(current_user: dict) -> str:
    return current_user.get("role_name", current_user.get("role", "user"))


def stock_scope_clause(current_user: dict, alias: str = "st") -> tuple[str, list[str]]:
    if role_name(current_user) != "user":
        return "", []

    location_ids = current_user.get("user_location_ids") or []
    locations = current_user.get("user_locations") or []
    values = [str(value) for value in (location_ids or locations) if value]
    if not values:
        return " AND 1 = 0", []

    column = f"{alias}.location_id" if location_ids else f"{alias}.location"
    placeholders = ", ".join(["?"] * len(values))
    return f" AND {column} IN ({placeholders})", values


def display_category(category: str | None) -> str:
    if not category:
        return "Uncategorized"
    words = category.replace("_", " ").replace("-", " ").split()
    return " ".join(word.upper() if len(word) <= 2 else word.capitalize() for word in words)


def get_part_rows(connection: sqlite3.Connection, current_user: dict) -> list[sqlite3.Row]:
    query = """
    SELECT
        p.id,
        p.sku,
        p.part_name,
        p.category,
        p.seasonality_profile,
        p.base_demand,
        p.supplier_id,
        COALESCE(s.supplier_name, p.supplier_id, 'Unknown Supplier') AS supplier,
        p.unit_price,
        p.salary_sensitivity,
        p.lead_time_days,
        p.min_order_qty,
        p.criticality
    FROM parts p
    LEFT JOIN suppliers s ON s.id = p.supplier_id
    ORDER BY p.part_name, p.sku
    """
    return connection.execute(query).fetchall()


def get_stock_rows_for_parts(
    connection: sqlite3.Connection,
    current_user: dict,
    part_ids: list[int],
) -> dict[int, list[sqlite3.Row]]:
    if not part_ids:
        return {}

    if role_name(current_user) == "user":
        ensure_user_stock_schema(connection)
        if not current_user.get("id"):
            return {}
        return get_user_stock_rows_for_parts(connection, current_user, part_ids)

    scope_clause, scope_params = stock_scope_clause(current_user, "st")
    placeholders = ", ".join(["?"] * len(part_ids))
    rows = connection.execute(
        f"""
        SELECT
            st.part_id,
            st.location,
            st.location_id,
            st.city,
            st.country_code,
            st.current_stock,
            st.reorder_point,
            st.safety_stock,
            st.optimal_stock,
            st.min_order_qty,
            st.lead_time_days,
            st.pending_order_qty,
            st.last_updated
        FROM stock st
        WHERE st.part_id IN ({placeholders})
        {scope_clause}
        ORDER BY
            st.part_id,
            CASE WHEN st.current_stock <= st.reorder_point THEN 0 ELSE 1 END,
            st.current_stock ASC,
            st.location_id,
            st.location
        """,
        [*part_ids, *scope_params],
    ).fetchall()

    by_part: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        by_part.setdefault(row["part_id"], []).append(row)
    return by_part


def stock_location_to_dict(row: sqlite3.Row) -> dict:
    current = int(row["current_stock"] or 0)
    reorder_point = int(row["reorder_point"] or 0)
    optimal_stock = int(row["optimal_stock"] or 0)
    recommended = max(optimal_stock, reorder_point, 1)
    availability = "available" if current > 0 else "order-only"
    return {
        "location": row["location_id"] or row["location"],
        "location_id": row["location_id"],
        "display_location": row["city"] or row["location"],
        "city": row["city"],
        "country_code": row["country_code"],
        "current_stock": current,
        "stock": current,
        "reorder_point": reorder_point,
        "safety_stock": int(row["safety_stock"] or 0),
        "optimal_stock": optimal_stock,
        "recommended": recommended,
        "min_order_qty": int(row["min_order_qty"] or 0),
        "lead_time_days": int(row["lead_time_days"] or 0),
        "pending_order_qty": int(row["pending_order_qty"] or 0),
        "status": catalog_stock_status(current, recommended, availability),
        "availability": availability,
        "last_updated": row["last_updated"],
    }


def part_to_catalog_item(part: sqlite3.Row, stock_rows: list[sqlite3.Row]) -> dict:
    locations = [stock_location_to_dict(row) for row in stock_rows]
    total_stock = sum(location["current_stock"] for location in locations)
    recommended = sum(location["recommended"] for location in locations)
    if not locations:
        recommended = max(int(part["min_order_qty"] or 0), 1)

    availability = "available" if total_stock > 0 else "order-only"
    preferred_location = locations[0] if locations else None
    category = display_category(part["category"])
    status = catalog_stock_status(total_stock, recommended, availability)

    return {
        "id": str(part["id"]),
        "part_id": part["id"],
        "productId": str(part["id"]),
        "sku": part["sku"],
        "name": part["part_name"],
        "part_name": part["part_name"],
        "category": category,
        "raw_category": part["category"],
        "supplier": part["supplier"],
        "supplier_id": part["supplier_id"],
        "stock": total_stock,
        "current_stock": total_stock,
        "recommended": recommended,
        "unitPrice": float(part["unit_price"] or 0),
        "unit_price": float(part["unit_price"] or 0),
        "status": status,
        "availability": availability,
        "location": preferred_location["location"] if preferred_location else None,
        "display_location": preferred_location["display_location"] if preferred_location else None,
        "leadTimeDays": int(part["lead_time_days"] or 0),
        "lead_time_days": int(part["lead_time_days"] or 0),
        "minOrderQty": int(part["min_order_qty"] or 0),
        "min_order_qty": int(part["min_order_qty"] or 0),
        "criticality": int(part["criticality"] or 3),
        "seasonality_profile": part["seasonality_profile"],
        "location_count": len(locations),
        "locations": locations,
        "catalog_available": True,
        "orderable": bool(part["supplier_id"]),
        "can_order_supplier": bool(part["supplier_id"]),
    }


def matches_catalog_filters(
    item: dict,
    *,
    search: str | None,
    category: str | None,
    supplier: str | None,
    status: str | None,
    availability: str | None,
) -> bool:
    if search:
        term = search.lower()
        haystack = " ".join(
            str(value)
            for value in [
                item["name"],
                item["sku"],
                item["category"],
                item["raw_category"],
                item["supplier"],
                item["supplier_id"],
            ]
            if value
        ).lower()
        if term not in haystack:
            return False

    if category and category.lower() not in {item["category"].lower(), str(item["raw_category"]).lower()}:
        return False
    if supplier and supplier.lower() not in {item["supplier"].lower(), str(item["supplier_id"]).lower()}:
        return False
    if status and item["status"].lower() != status.lower():
        return False
    if availability and item["availability"].lower() != availability.lower():
        return False
    return True


def list_catalog_parts(
    connection: sqlite3.Connection,
    current_user: dict,
    *,
    search: str | None = None,
    category: str | None = None,
    supplier: str | None = None,
    status: str | None = None,
    availability: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[dict]:
    parts = get_part_rows(connection, current_user)
    stock_by_part = get_stock_rows_for_parts(connection, current_user, [row["id"] for row in parts])
    catalog = [
        part_to_catalog_item(part, stock_by_part.get(part["id"], []))
        for part in parts
    ]
    filtered = [
        item
        for item in catalog
        if matches_catalog_filters(
            item,
            search=search,
            category=category,
            supplier=supplier,
            status=status,
            availability=availability,
        )
    ]
    return filtered[offset : offset + limit]


def get_catalog_part(connection: sqlite3.Connection, current_user: dict, part_id: int) -> dict | None:
    parts = [row for row in get_part_rows(connection, current_user) if row["id"] == part_id]
    if not parts:
        return None
    stock_by_part = get_stock_rows_for_parts(connection, current_user, [part_id])
    return part_to_catalog_item(parts[0], stock_by_part.get(part_id, []))


def get_catalog_filters(connection: sqlite3.Connection, current_user: dict) -> dict:
    catalog = list_catalog_parts(connection, current_user, limit=10000)
    return {
        "categories": sorted({item["category"] for item in catalog}),
        "suppliers": sorted({item["supplier"] for item in catalog}),
        "statuses": sorted({item["status"] for item in catalog}),
        "availability": sorted({item["availability"] for item in catalog}),
    }
