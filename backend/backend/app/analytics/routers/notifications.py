from fastapi import APIRouter, Depends, Query

from app.core.auth import require_authenticated_user
from app.db import get_connection
from app.inventory.services.order_access import role_name, scoped_location_clause
from app.inventory.services.order_workflows import (
    maybe_generate_incoming_order,
    order_stream_cutoff,
    release_due_supplier_orders,
    seed_demo_order_workflows,
)


router = APIRouter()


def order_scope_clause(current_user: dict, column: str = "location") -> tuple[str, list[object]]:
    if role_name(current_user) == "user":
        return " AND user_id = ?", [current_user["id"]]
    return scoped_location_clause(current_user, column)


def order_quantity(connection, line_table: str, order_id: str) -> int:
    row = connection.execute(
        f"SELECT COALESCE(SUM(quantity), 0) FROM {line_table} WHERE order_id = ?",
        (order_id,),
    ).fetchone()
    return int(row[0] or 0)


def order_notification_watermark(connection, current_user: dict) -> str | None:
    if role_name(current_user) != "user" or not current_user.get("id"):
        return None

    order_stream_cutoff(connection, current_user)
    row = connection.execute(
        """
        SELECT last_generated_at, created_at
        FROM order_notification_stream
        WHERE user_id = ?
        """,
        (current_user["id"],),
    ).fetchone()
    if row is None:
        return None
    return row["last_generated_at"] or row["created_at"]


@router.get("/notifications")
def get_notifications(
    current_user: dict = Depends(require_authenticated_user),
    generate: bool = Query(False, description="Allow the timed demo order stream to create one new order if due."),
):
    connection = get_connection()
    try:
        seed_demo_order_workflows(connection)
        if generate:
            maybe_generate_incoming_order(connection, current_user)
        release_due_supplier_orders(connection, current_user)
        notifications: list[dict] = []

        client_clause, client_params = order_scope_clause(current_user)
        watermark = order_notification_watermark(connection, current_user)
        stream_clause = " AND created_at >= ?" if watermark else ""
        stream_params = [watermark] if watermark else []
        client_rows = connection.execute(
            f"""
            SELECT id, client_name, status, created_at, shortage_quantity
            FROM order_clients
            WHERE status IN ('Pending', 'Scheduled')
            {client_clause}
            {stream_clause}
            ORDER BY created_at DESC
            """,
            [*client_params, *stream_params],
        ).fetchall()
        for row in client_rows:
            quantity = order_quantity(connection, "order_client_lines", row["id"])
            notifications.append(
                {
                    "id": f"WF-CLIENT-{row['id']}",
                    "type": "client-order",
                    "severity": "critical" if int(row["shortage_quantity"] or 0) > 0 else "warning",
                    "title": "Client order scheduled" if row["status"] == "Scheduled" else "Client order needs review",
                    "message": f"{row['client_name']} requested {quantity} part{'s' if quantity != 1 else ''}. Approve, refuse, or schedule the order.",
                    "createdAt": row["created_at"],
                    "created_at": row["created_at"],
                    "read": False,
                    "route": "/dashboard/orders?tab=clients&group=needs-review",
                    "relatedId": row["id"],
                    "related_id": row["id"],
                }
            )

        backorder_rows = connection.execute(
            f"""
            SELECT id, client_name, fulfillment_status, shortage_quantity, updated_at
            FROM order_clients
            WHERE status = 'Approved'
              AND fulfillment_status IN ('partial', 'backorder', 'ready')
            {client_clause}
            ORDER BY updated_at DESC
            """,
            client_params,
        ).fetchall()
        for row in backorder_rows:
            quantity = order_quantity(connection, "order_client_lines", row["id"])
            is_ready = row["fulfillment_status"] == "ready" and int(row["shortage_quantity"] or 0) == 0
            notifications.append(
                {
                    "id": f"WF-BACKORDER-{row['id']}",
                    "type": "backorder",
                    "severity": "info" if is_ready else "warning",
                    "title": "Backorder ready to complete" if is_ready else "Backorder waiting on supplier",
                    "message": (
                        f"{row['client_name']} can now be completed. {quantity} part{'s' if quantity != 1 else ''} are allocated."
                        if is_ready
                        else f"{row['client_name']} is waiting for {row['shortage_quantity']} missing part{'s' if int(row['shortage_quantity'] or 0) != 1 else ''}."
                    ),
                    "createdAt": row["updated_at"],
                    "created_at": row["updated_at"],
                    "read": False,
                    "route": f"/dashboard/orders?tab=clients&group={'backorders-ready' if is_ready else 'backorders-waiting'}",
                    "relatedId": row["id"],
                    "related_id": row["id"],
                }
            )

        supplier_clause, supplier_params = order_scope_clause(current_user)
        supplier_rows = connection.execute(
            f"""
            SELECT id, supplier_name, status, created_at, received_at, updated_at, stock_applied
            FROM order_suppliers
            WHERE status = 'Delivered'
              AND stock_applied = 0
            {supplier_clause}
            ORDER BY created_at DESC
            """,
            supplier_params,
        ).fetchall()
        for row in supplier_rows:
            quantity = order_quantity(connection, "order_supplier_lines", row["id"])
            created_at = row["updated_at"] or row["received_at"] or row["created_at"]
            notifications.append(
                {
                    "id": f"WF-SUPPLIER-{row['id']}",
                    "type": "supplier-delivery",
                    "severity": "warning",
                    "title": "Supplier delivery needs review",
                    "message": f"{row['supplier_name']} arrived with {quantity} part{'s' if quantity != 1 else ''}. Receive, postpone, or refuse it.",
                    "createdAt": created_at,
                    "created_at": created_at,
                    "read": False,
                    "route": "/dashboard/orders?tab=suppliers&group=needs-review",
                    "relatedId": row["id"],
                    "related_id": row["id"],
                }
            )

        stock_rows = connection.execute(
            """
            SELECT
                a.id,
                p.part_name,
                a.severity,
                a.message,
                a.created_at
            FROM notifications a
            JOIN parts p ON p.id = a.part_id
            ORDER BY a.created_at DESC
            LIMIT 20
            """
        ).fetchall()
        for row in stock_rows:
            notifications.append(
                {
                    "id": f"STOCK-{row['id']}",
                    "type": "market",
                    "severity": row["severity"] if row["severity"] in {"info", "warning", "critical"} else "info",
                    "title": f"{row['part_name']} stock alert",
                    "message": row["message"],
                    "createdAt": row["created_at"],
                    "created_at": row["created_at"],
                    "read": False,
                    "route": "/dashboard/stock",
                    "relatedId": str(row["id"]),
                    "related_id": str(row["id"]),
                }
            )

        return sorted(notifications, key=lambda item: item["createdAt"], reverse=True)[:30]
    finally:
        connection.close()
