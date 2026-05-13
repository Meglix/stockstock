from __future__ import annotations

from datetime import datetime
import sqlite3

from app.inventory.services.order_workflows import ensure_order_workflow_schema, order_stream_cutoff, release_due_supplier_orders
from app.inventory.services.stock_status import stock_health
from app.inventory.services.user_stock import ensure_user_stock_schema


SERIES_COLORS = [
    "#fb923c",
    "#facc15",
    "#94a3b8",
    "#f87171",
    "#38bdf8",
    "#a7f3d0",
]

COUNTRY_META = {
    "DE": {"country": "Germany", "city": "Stuttgart", "x": 525, "y": 115},
    "FR": {"country": "France", "city": "Paris", "x": 507, "y": 114},
    "IT": {"country": "Italy", "city": "Milan", "x": 526, "y": 124},
    "ES": {"country": "Spain", "city": "Madrid", "x": 490, "y": 138},
    "NL": {"country": "Netherlands", "city": "Amsterdam", "x": 514, "y": 105},
    "PL": {"country": "Poland", "city": "Warsaw", "x": 558, "y": 105},
    "RO": {"country": "Romania", "city": "Bucharest", "x": 573, "y": 127},
    "CZ": {"country": "Czechia", "city": "Prague", "x": 540, "y": 111},
}


def role_name(current_user: dict) -> str:
    return current_user.get("role_name", current_user.get("role", "user"))


def location_scope(current_user: dict, column_by_kind: dict[str, str]) -> tuple[str, list[str]]:
    if role_name(current_user) != "user":
        return "", []

    location_ids = current_user.get("user_location_ids") or []
    locations = current_user.get("user_locations") or []
    values = [str(value) for value in (location_ids or locations) if value]
    if not values:
        return " AND 1 = 0", []

    column = column_by_kind["location_id"] if location_ids else column_by_kind["location"]
    placeholders = ", ".join(["?"] * len(values))
    return f" AND {column} IN ({placeholders})", values


def requested_location_scope(requested_location: str | None, column_by_kind: dict[str, str]) -> tuple[str, list[str]]:
    if requested_location is None:
        return "", []

    value = requested_location.strip()
    if not value:
        return "", []

    location_id_column = column_by_kind["location_id"]
    location_column = column_by_kind["location"]
    if location_id_column == location_column:
        return f" AND {location_id_column} = ?", [value]

    return f" AND ({location_id_column} = ? OR {location_column} = ?)", [value, value]


def stream_scope(connection: sqlite3.Connection, current_user: dict, column: str = "created_at") -> tuple[str, list[object]]:
    cutoff = order_stream_cutoff(connection, current_user)
    if cutoff is None:
        return "", []
    return f" AND {column} >= ?", [cutoff]


def month_label(month_key: str) -> str:
    try:
        return datetime.strptime(month_key, "%Y-%m").strftime("%b")
    except ValueError:
        return month_key


def display_category(category: str | None) -> str:
    if not category:
        return "Uncategorized"
    words = category.replace("_", " ").replace("-", " ").split()
    return " ".join(word.upper() if len(word) <= 2 else word.capitalize() for word in words)


def get_dashboard_kpis(connection: sqlite3.Connection, current_user: dict) -> dict:
    if role_name(current_user) == "user":
        ensure_user_stock_schema(connection)
        user_id = current_user["id"]
        order_stream_clause, order_stream_params = stream_scope(connection, current_user)
        total_available_parts = connection.execute(
            """
            SELECT COALESCE(SUM(current_stock), 0)
            FROM user_stock
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()[0]
        categories = connection.execute("SELECT COUNT(DISTINCT category) FROM parts").fetchone()[0]
        pending_client_orders = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM order_clients
            WHERE user_id = ?
              AND status IN ('Pending', 'Scheduled')
              {order_stream_clause}
            """,
            [user_id, *order_stream_params],
        ).fetchone()[0]
        pending_supplier_orders = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM order_suppliers
            WHERE user_id = ?
              AND status = 'Delivered'
              AND stock_applied = 0
              {order_stream_clause}
            """,
            [user_id, *order_stream_params],
        ).fetchone()[0]
        critical_stock_alerts = connection.execute(
            """
            SELECT COUNT(*)
            FROM user_stock
            WHERE user_id = ?
              AND (
                current_stock <= reorder_point
                OR current_stock <= optimal_stock * 0.58
              )
            """,
            (user_id,),
        ).fetchone()[0]

        return {
            "total_available_parts": int(total_available_parts or 0),
            "categories": int(categories or 0),
            "pending_client_orders": int(pending_client_orders or 0),
            "pending_supplier_orders": int(pending_supplier_orders or 0),
            "critical_stock_alerts": int(critical_stock_alerts or 0),
        }

    stock_clause, stock_params = location_scope(
        current_user,
        {"location_id": "st.location_id", "location": "st.location"},
    )
    order_clause, order_params = location_scope(
        current_user,
        {"location_id": "location", "location": "location"},
    )

    total_available_parts = connection.execute(
        f"""
        SELECT COALESCE(SUM(st.current_stock), 0)
        FROM stock st
        WHERE 1=1
        {stock_clause}
        """,
        stock_params,
    ).fetchone()[0]

    categories = connection.execute(
        f"""
        SELECT COUNT(DISTINCT p.category)
        FROM parts p
        WHERE EXISTS (
            SELECT 1
            FROM stock st
            WHERE st.part_id = p.id
            {stock_clause}
        )
        """,
        stock_params,
    ).fetchone()[0]

    pending_client_orders = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM order_clients
        WHERE status IN ('Pending', 'Scheduled')
        {order_clause}
        """,
        order_params,
    ).fetchone()[0]

    pending_supplier_orders = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM order_suppliers
        WHERE status = 'Delivered'
          AND stock_applied = 0
        {order_clause}
        """,
        order_params,
    ).fetchone()[0]

    critical_stock_alerts = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM stock st
        WHERE st.current_stock <= st.reorder_point
        {stock_clause}
        """,
        stock_params,
    ).fetchone()[0]

    return {
        "total_available_parts": int(total_available_parts or 0),
        "categories": int(categories or 0),
        "pending_client_orders": int(pending_client_orders or 0),
        "pending_supplier_orders": int(pending_supplier_orders or 0),
        "critical_stock_alerts": int(critical_stock_alerts or 0),
    }


def get_runtime_sales_flow(
    connection: sqlite3.Connection,
    current_user: dict,
    months_count: int,
    category_limit: int,
    selected_category: str | None,
) -> dict | None:
    ensure_order_workflow_schema(connection)

    where_clause = "WHERE 1=1"
    params: list[object] = []
    if role_name(current_user) == "user":
        if not current_user.get("id"):
            return None
        where_clause += " AND user_id = ?"
        params.append(current_user["id"])
    else:
        sales_clause, sales_params = location_scope(
            current_user,
            {"location_id": "location", "location": "location"},
        )
        where_clause += sales_clause
        params.extend(sales_params)

    month_rows = connection.execute(
        f"""
        SELECT substr(sold_at, 1, 7) AS month_key
        FROM order_sales_events
        {where_clause}
        GROUP BY month_key
        ORDER BY month_key DESC
        LIMIT ?
        """,
        [*params, months_count],
    ).fetchall()
    month_keys = [row["month_key"] for row in reversed(month_rows)]
    if not month_keys:
        return None

    month_placeholders = ", ".join(["?"] * len(month_keys))
    category_rows = connection.execute(
        f"""
        SELECT category, SUM(quantity_sold) AS total_sold
        FROM order_sales_events
        {where_clause}
          AND substr(sold_at, 1, 7) IN ({month_placeholders})
        GROUP BY category
        ORDER BY total_sold DESC
        LIMIT ?
        """,
        [*params, *month_keys, category_limit],
    ).fetchall()
    category_options_rows = connection.execute(
        f"""
        SELECT category, SUM(quantity_sold) AS total_sold
        FROM order_sales_events
        {where_clause}
          AND substr(sold_at, 1, 7) IN ({month_placeholders})
        GROUP BY category
        ORDER BY total_sold DESC
        """,
        [*params, *month_keys],
    ).fetchall()

    categories = [row["category"] for row in category_rows]
    category_options = [
        {
            "category": display_category(row["category"]),
            "raw_category": row["category"],
            "total_sold": int(row["total_sold"] or 0),
        }
        for row in category_options_rows
    ]

    selected_raw_category = None
    if selected_category:
        normalized = selected_category.strip().lower()
        for row in category_options_rows:
            raw = row["category"] or ""
            if raw.lower() == normalized or display_category(raw).lower() == normalized:
                selected_raw_category = raw
                break
        if selected_raw_category and selected_raw_category not in categories:
            categories = [selected_raw_category, *categories]
            categories = categories[: max(category_limit, 1)]

    if not categories:
        return None

    category_placeholders = ", ".join(["?"] * len(categories))
    value_rows = connection.execute(
        f"""
        SELECT
            category,
            substr(sold_at, 1, 7) AS month_key,
            SUM(quantity_sold) AS quantity
        FROM order_sales_events
        {where_clause}
          AND substr(sold_at, 1, 7) IN ({month_placeholders})
          AND category IN ({category_placeholders})
        GROUP BY category, month_key
        """,
        [*params, *month_keys, *categories],
    ).fetchall()

    values_by_category_month = {
        (row["category"], row["month_key"]): int(row["quantity"] or 0)
        for row in value_rows
    }

    return {
        "months": [month_label(key) for key in month_keys],
        "series": [
            {
                "category": display_category(category),
                "raw_category": category,
                "color": SERIES_COLORS[index % len(SERIES_COLORS)],
                "total_sold": sum(values_by_category_month.get((category, month_key), 0) for month_key in month_keys),
                "values": [values_by_category_month.get((category, month_key), 0) for month_key in month_keys],
            }
            for index, category in enumerate(categories)
        ],
        "category_options": category_options,
        "selected_category": display_category(selected_raw_category) if selected_raw_category else None,
        "source": "runtime_orders",
    }


def get_sales_flow(
    connection: sqlite3.Connection,
    current_user: dict,
    months_count: int = 6,
    category_limit: int = 6,
    selected_category: str | None = None,
    requested_location: str | None = None,
) -> dict:
    if not requested_location:
        runtime_sales = get_runtime_sales_flow(connection, current_user, months_count, category_limit, selected_category)
        if runtime_sales is not None:
            return runtime_sales

    if requested_location:
        sales_clause, sales_params = requested_location_scope(
            requested_location,
            {"location_id": "location_id", "location": "city"},
        )
    else:
        sales_clause, sales_params = location_scope(
            current_user,
            {"location_id": "location_id", "location": "city"},
        )
        if role_name(current_user) == "user" and not (current_user.get("user_location_ids") or current_user.get("user_locations")):
            sales_clause, sales_params = "", []

    month_rows = connection.execute(
        f"""
        SELECT substr(date, 1, 7) AS month_key
        FROM sales_history
        WHERE date IS NOT NULL
        {sales_clause}
        GROUP BY month_key
        ORDER BY month_key DESC
        LIMIT ?
        """,
        [*sales_params, months_count],
    ).fetchall()
    month_keys = [row["month_key"] for row in reversed(month_rows)]
    if not month_keys:
        return {"months": [], "series": [], "category_options": [], "selected_category": None}

    month_placeholders = ", ".join(["?"] * len(month_keys))
    category_rows = connection.execute(
        f"""
        SELECT category, SUM(quantity_sold) AS total_sold
        FROM sales_history
        WHERE substr(date, 1, 7) IN ({month_placeholders})
        {sales_clause}
        GROUP BY category
        ORDER BY total_sold DESC
        LIMIT ?
        """,
        [*month_keys, *sales_params, category_limit],
    ).fetchall()
    categories = [row["category"] for row in category_rows]
    category_options_rows = connection.execute(
        f"""
        SELECT category, SUM(quantity_sold) AS total_sold
        FROM sales_history
        WHERE substr(date, 1, 7) IN ({month_placeholders})
        {sales_clause}
        GROUP BY category
        ORDER BY total_sold DESC
        """,
        [*month_keys, *sales_params],
    ).fetchall()
    category_options = [
        {
            "category": display_category(row["category"]),
            "raw_category": row["category"],
            "total_sold": int(row["total_sold"] or 0),
        }
        for row in category_options_rows
    ]
    selected_raw_category = None
    if selected_category:
        normalized = selected_category.strip().lower()
        for row in category_options_rows:
            raw = row["category"] or ""
            if raw.lower() == normalized or display_category(raw).lower() == normalized:
                selected_raw_category = raw
                break
        if selected_raw_category and selected_raw_category not in categories:
            categories = [selected_raw_category, *categories]
            categories = categories[: max(category_limit, 1)]

    if not categories:
        return {
            "months": [month_label(key) for key in month_keys],
            "series": [],
            "category_options": category_options,
            "selected_category": display_category(selected_raw_category) if selected_raw_category else None,
        }

    category_placeholders = ", ".join(["?"] * len(categories))
    value_rows = connection.execute(
        f"""
        SELECT
            category,
            substr(date, 1, 7) AS month_key,
            SUM(quantity_sold) AS quantity
        FROM sales_history
        WHERE substr(date, 1, 7) IN ({month_placeholders})
          AND category IN ({category_placeholders})
          {sales_clause}
        GROUP BY category, month_key
        """,
        [*month_keys, *categories, *sales_params],
    ).fetchall()

    values_by_category_month = {
        (row["category"], row["month_key"]): int(row["quantity"] or 0)
        for row in value_rows
    }

    return {
        "months": [month_label(key) for key in month_keys],
        "series": [
            {
                "category": display_category(category),
                "raw_category": category,
                "color": SERIES_COLORS[index % len(SERIES_COLORS)],
                "total_sold": sum(values_by_category_month.get((category, month_key), 0) for month_key in month_keys),
                "values": [values_by_category_month.get((category, month_key), 0) for month_key in month_keys],
            }
            for index, category in enumerate(categories)
        ],
        "category_options": category_options,
        "selected_category": display_category(selected_raw_category) if selected_raw_category else None,
    }


def get_priority_stock(connection: sqlite3.Connection, current_user: dict, limit: int = 5) -> list[dict]:
    if role_name(current_user) == "user":
        ensure_user_stock_schema(connection)
        rows = connection.execute(
            """
            SELECT
                us.part_id,
                p.sku,
                p.part_name,
                p.category,
                COALESCE(s.supplier_name, p.supplier_id, 'Unknown Supplier') AS supplier,
                us.location,
                us.location_id,
                us.current_stock,
                us.reorder_point,
                us.optimal_stock
            FROM user_stock us
            JOIN parts p ON p.id = us.part_id
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            WHERE us.user_id = ?
              AND (
                us.current_stock <= us.reorder_point
                OR us.current_stock <= us.optimal_stock * 0.78
              )
            ORDER BY
                CASE
                    WHEN us.current_stock <= us.reorder_point THEN 0
                    ELSE 1
                END,
                us.current_stock ASC,
                us.reorder_point DESC
            LIMIT ?
            """,
            (current_user["id"], limit),
        ).fetchall()

        items = []
        for row in rows:
            current = int(row["current_stock"] or 0)
            reorder_point = int(row["reorder_point"] or 0)
            optimal = int(row["optimal_stock"] or 0)
            recommended = max(optimal, reorder_point, 1)
            items.append(
                {
                    "id": f"user-stock-{current_user['id']}-{row['part_id']}",
                    "product_id": str(row["part_id"]),
                    "part_id": row["part_id"],
                    "sku": row["sku"],
                    "name": row["part_name"],
                    "part_name": row["part_name"],
                    "category": display_category(row["category"]),
                    "supplier": row["supplier"],
                    "current": current,
                    "recommended": recommended,
                    "reorder_point": reorder_point,
                    "status": stock_health(current, optimal, reorder_point),
                    "location": row["location_id"] or row["location"],
                    "location_id": row["location_id"],
                }
            )
        return items

    stock_clause, stock_params = location_scope(
        current_user,
        {"location_id": "st.location_id", "location": "st.location"},
    )

    rows = connection.execute(
        f"""
        SELECT
            st.part_id,
            p.sku,
            p.part_name,
            p.category,
            COALESCE(s.supplier_name, p.supplier_id, 'Unknown Supplier') AS supplier,
            st.location,
            st.location_id,
            st.current_stock,
            st.reorder_point,
            st.optimal_stock
        FROM stock st
        JOIN parts p ON p.id = st.part_id
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        WHERE (
            st.current_stock <= st.reorder_point
            OR st.current_stock <= st.optimal_stock * 0.78
        )
        {stock_clause}
        ORDER BY
            CASE
                WHEN st.current_stock <= st.reorder_point THEN 0
                ELSE 1
            END,
            st.current_stock ASC,
            st.reorder_point DESC
        LIMIT ?
        """,
        [*stock_params, limit],
    ).fetchall()

    items = []
    for row in rows:
        current = int(row["current_stock"] or 0)
        reorder_point = int(row["reorder_point"] or 0)
        optimal = int(row["optimal_stock"] or 0)
        recommended = max(optimal, reorder_point, 1)
        items.append(
            {
                "id": f"stock-{row['part_id']}-{row['location_id'] or row['location']}",
                "product_id": str(row["part_id"]),
                "part_id": row["part_id"],
                "sku": row["sku"],
                "name": row["part_name"],
                "part_name": row["part_name"],
                "category": display_category(row["category"]),
                "supplier": row["supplier"],
                "current": current,
                "recommended": recommended,
                "reorder_point": reorder_point,
                "status": stock_health(current, optimal, reorder_point),
                "location": row["location_id"] or row["location"],
                "location_id": row["location_id"],
            }
        )
    return items


def get_supplier_map(connection: sqlite3.Connection, current_user: dict, limit: int = 8) -> list[dict]:
    if role_name(current_user) == "user":
        ensure_user_stock_schema(connection)
        rows = connection.execute(
            """
            SELECT
                s.id AS supplier_id,
                s.supplier_name,
                s.country_code,
                COUNT(DISTINCT p.id) AS part_count,
                COALESCE(SUM(us.current_stock), 0) AS available_units
            FROM suppliers s
            JOIN parts p ON p.supplier_id = s.id
            LEFT JOIN user_stock us ON us.part_id = p.id AND us.user_id = ?
            GROUP BY s.id, s.supplier_name, s.country_code
            ORDER BY available_units DESC, part_count DESC, s.supplier_name
            LIMIT ?
            """,
            (current_user["id"], limit),
        ).fetchall()

        locations = []
        for row in rows:
            country_code = row["country_code"] or "EU"
            meta = COUNTRY_META.get(country_code, {"country": country_code, "city": "European Hub", "x": 520, "y": 125})
            part_count = int(row["part_count"] or 0)
            available_units = int(row["available_units"] or 0)
            locations.append(
                {
                    "supplier": row["supplier_name"],
                    "supplier_id": row["supplier_id"],
                    "country": meta["country"],
                    "country_code": country_code,
                    "city": meta["city"],
                    "parts": part_count,
                    "catalog_parts": part_count,
                    "available_units": available_units,
                    "x": meta["x"],
                    "y": meta["y"],
                }
            )
        return locations

    stock_clause, stock_params = location_scope(
        current_user,
        {"location_id": "st.location_id", "location": "st.location"},
    )

    rows = connection.execute(
        f"""
        SELECT
            s.id AS supplier_id,
            s.supplier_name,
            s.country_code,
            COUNT(DISTINCT p.id) AS part_count,
            COALESCE(SUM(st.current_stock), 0) AS available_units
        FROM suppliers s
        JOIN parts p ON p.supplier_id = s.id
        LEFT JOIN stock st ON st.part_id = p.id
        WHERE 1=1
        {stock_clause}
        GROUP BY s.id, s.supplier_name, s.country_code
        ORDER BY available_units DESC, part_count DESC, s.supplier_name
        LIMIT ?
        """,
        [*stock_params, limit],
    ).fetchall()

    locations = []
    for row in rows:
        country_code = row["country_code"] or "EU"
        meta = COUNTRY_META.get(country_code, {"country": country_code, "city": "European Hub", "x": 520, "y": 125})
        part_count = int(row["part_count"] or 0)
        available_units = int(row["available_units"] or 0)
        locations.append(
            {
                "supplier": row["supplier_name"],
                "supplier_id": row["supplier_id"],
                "country": meta["country"],
                "country_code": country_code,
                "city": meta["city"],
                "parts": part_count,
                "catalog_parts": part_count,
                "available_units": available_units,
                "x": meta["x"],
                "y": meta["y"],
            }
        )
    return locations


def get_market_trends(
    connection: sqlite3.Connection,
    current_user: dict,
    limit: int = 5,
    requested_location: str | None = None,
) -> list[dict]:
    sales_flow = get_sales_flow(
        connection,
        current_user,
        months_count=2,
        category_limit=5,
        requested_location=requested_location,
    )
    trends: list[dict] = []

    for series in sales_flow["series"]:
        values = series["values"]
        if not values:
            continue
        latest = values[-1]
        previous = values[-2] if len(values) > 1 else 0
        if previous > 0:
            growth = round(((latest - previous) / previous) * 100)
        else:
            growth = 100 if latest > 0 else 0

        if growth >= 15:
            trends.append(
                {
                    "id": f"trend-growth-{series['category'].lower().replace(' ', '-')}",
                    "title": f"{series['category']} demand is accelerating",
                    "detail": f"Recent sales are up {growth}% versus the previous month, with {latest} units sold.",
                    "priority": "High",
                    "category": series["category"],
                }
            )
        elif growth <= -10:
            trends.append(
                {
                    "id": f"trend-decline-{series['category'].lower().replace(' ', '-')}",
                    "title": f"{series['category']} demand is slowing",
                    "detail": f"Recent sales are down {abs(growth)}% versus the previous month, with {latest} units sold.",
                    "priority": "Declining",
                    "category": series["category"],
                }
            )
        elif latest > 0:
            trends.append(
                {
                    "id": f"trend-stable-{series['category'].lower().replace(' ', '-')}",
                    "title": f"{series['category']} demand is steady",
                    "detail": f"Recent movement is stable at {latest} units in the latest month.",
                    "priority": "Stable",
                    "category": series["category"],
                }
            )

    low_stock = get_priority_stock(connection, current_user, limit=3)
    for item in low_stock:
        trends.append(
            {
                "id": f"trend-stock-{item['part_id']}-{item['location']}",
                "title": f"{item['category']} stock needs attention",
                "detail": f"{item['name']} has {item['current']} units at {item['location']} against a recommended {item['recommended']}.",
                "priority": "High" if item["status"] == "Critical" else "Medium",
                "category": item["category"],
            }
        )

    order_clause, order_params = location_scope(
        current_user,
        {"location_id": "location", "location": "location"},
    )
    order_stream_clause, order_stream_params = stream_scope(connection, current_user)
    delayed_suppliers = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM order_suppliers
        WHERE status = 'Delayed'
        {order_clause}
        {order_stream_clause}
        """,
        [*order_params, *order_stream_params],
    ).fetchone()[0]
    if delayed_suppliers:
        trends.append(
            {
                "id": "trend-supplier-delays",
                "title": "Supplier delivery delays are active",
                "detail": f"{delayed_suppliers} supplier order(s) are currently delayed and may affect replenishment timing.",
                "priority": "Medium",
                "category": "Suppliers",
            }
        )

    deduped = []
    seen = set()
    for trend in trends:
        if trend["id"] in seen:
            continue
        seen.add(trend["id"])
        deduped.append(trend)
        if len(deduped) >= limit:
            break
    return deduped


def get_dashboard_summary(connection: sqlite3.Connection, current_user: dict) -> dict:
    release_due_supplier_orders(connection, current_user)
    return {
        "kpis": get_dashboard_kpis(connection, current_user),
        "sales_flow": get_sales_flow(connection, current_user),
        "market_trends": get_market_trends(connection, current_user),
        "supplier_locations": get_supplier_map(connection, current_user),
        "priority_stock": get_priority_stock(connection, current_user),
    }
