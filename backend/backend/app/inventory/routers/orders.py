import random

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import get_current_user
from app.db import get_connection
from app.inventory.schemas.orders import (
    ClientOrderCreatePayload,
    ClientOrderSchedulePayload,
    SupplierOrderCreatePayload,
    SupplierOrderPostponePayload,
    WorkflowOrderLinePayload,
)
from app.inventory.services.order_access import (
    require_order_location_access,
    require_order_record_access,
    require_payload_location_for_scoped_user,
    role_name,
    scoped_location_clause,
)
from app.inventory.services.order_workflows import (
    CLIENT_STATUSES,
    SUPPLIER_STATUSES,
    apply_client_order_stock,
    apply_supplier_order_stock,
    client_order_to_dict,
    create_client_order_record,
    create_supplier_replenishments_for_client_shortage,
    create_supplier_order_record,
    fetch_client_order,
    fetch_supplier_order,
    order_stream_cutoff,
    parse_clock_time,
    record_client_order_sales,
    release_due_supplier_orders,
    seed_demo_order_workflows,
    supplier_order_to_dict,
    utc_now_iso as workflow_utc_now_iso,
)

router = APIRouter(prefix="/orders", tags=["orders"])


def include_demo_order_clause(
    current_user: dict,
    user_column: str = "user_id",
    location_column: str = "location",
) -> tuple[str, list[object]]:
    if role_name(current_user) == "user":
        return f" AND {user_column} = ?", [current_user["id"]]
    return scoped_location_clause(current_user, location_column)


def user_stream_clause(db, current_user: dict, column: str = "created_at") -> tuple[str, list[object]]:
    cutoff = order_stream_cutoff(db, current_user)
    if cutoff is None:
        return "", []
    return f" AND {column} >= ?", [cutoff]


def claim_demo_order_for_user(db, table: str, order_id: str, current_user: dict) -> None:
    if role_name(current_user) != "user":
        return
    if table not in {"order_clients", "order_suppliers"}:
        raise ValueError("Unsupported order workflow table")

    db.execute(
        f"UPDATE {table} SET user_id = ?, updated_at = ? WHERE id = ? AND user_id IS NULL",
        (current_user["id"], workflow_utc_now_iso(), order_id),
    )


def require_demo_or_owned_order_access(current_user: dict, order: dict) -> None:
    if role_name(current_user) == "user" and order["user_id"] is None:
        return
    require_order_record_access(current_user, order)


def client_order_availability(db, order, current_user: dict) -> dict:
    available_by_part: dict[int, int] = {}
    shortages = []
    total_requested = 0
    total_allocated = 0
    total_missing = 0

    lines = db.execute(
        """
        SELECT part_id, sku, part_name, quantity
        FROM order_client_lines
        WHERE order_id = ?
        ORDER BY id
        """,
        (order["id"],),
    ).fetchall()

    for line in lines:
        part_id = int(line["part_id"])
        if part_id not in available_by_part:
            if role_name(current_user) == "user":
                stock = db.execute(
                    """
                    SELECT current_stock
                    FROM user_stock
                    WHERE user_id = ? AND part_id = ?
                    """,
                    (current_user["id"], part_id),
                ).fetchone()
            elif order["user_id"] is not None:
                stock = db.execute(
                    """
                    SELECT current_stock
                    FROM user_stock
                    WHERE user_id = ? AND part_id = ?
                    """,
                    (order["user_id"], part_id),
                ).fetchone()
            else:
                stock = db.execute(
                    """
                    SELECT current_stock
                    FROM stock
                    WHERE part_id = ? AND (location = ? OR location_id = ?)
                    """,
                    (part_id, order["location"], order["location"]),
                ).fetchone()
            available_by_part[part_id] = int(stock["current_stock"]) if stock is not None else 0

        requested = int(line["quantity"])
        available = available_by_part[part_id]
        allocated = min(available, requested)
        missing = requested - allocated
        available_by_part[part_id] = max(0, available - requested)
        total_requested += requested
        total_allocated += allocated
        total_missing += missing

        if missing > 0:
            shortages.append(
                {
                    "productId": str(part_id),
                    "product_id": part_id,
                    "part_id": part_id,
                    "name": line["part_name"],
                    "part_name": line["part_name"],
                    "sku": line["sku"],
                    "requested": requested,
                    "available": available,
                    "missing": missing,
                }
            )

    if total_missing == 0:
        fulfillment_status = "fulfilled"
    elif total_allocated == 0 and total_requested > 0:
        fulfillment_status = "backorder"
    else:
        fulfillment_status = "partial"

    return {
        "order_id": order["id"],
        "can_fulfill": total_missing == 0,
        "fulfillment_status": fulfillment_status,
        "total_requested": total_requested,
        "total_allocated": total_allocated,
        "total_missing": total_missing,
        "shortages": shortages,
    }


@router.get("/clients")
def list_client_orders(
    current_user: dict = Depends(get_current_user),
    status: str | None = Query(None, description="Filter by client order status"),
    location: str | None = Query(None, description="Filter by location/location_id"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    db = get_connection()
    try:
        seed_demo_order_workflows(db)
        query = "SELECT * FROM order_clients WHERE 1=1"
        params: list[object] = []

        if status:
            if status not in CLIENT_STATUSES:
                raise HTTPException(status_code=422, detail="Invalid client order status")
            query += " AND status = ?"
            params.append(status)
        elif role_name(current_user) == "user":
            query += """
                AND (
                    status IN ('Pending', 'Scheduled', 'Denied', 'Delivered')
                    OR (status = 'Approved' AND fulfillment_status IN ('partial', 'backorder', 'ready'))
                )
            """

        if location:
            if role_name(current_user) != "user":
                require_order_location_access(current_user, location)
            query += " AND location = ?"
            params.append(location)
        clause, scope_params = include_demo_order_clause(current_user)
        query += clause
        params.extend(scope_params)
        stream_clause, stream_params = user_stream_clause(db, current_user)
        query += stream_clause
        params.extend(stream_params)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = db.execute(query, params).fetchall()
        return [client_order_to_dict(db, row) for row in rows]
    finally:
        db.close()

@router.post("/clients", status_code=201)
def create_client_order(
    payload: ClientOrderCreatePayload,
    current_user: dict = Depends(get_current_user),
):
    require_payload_location_for_scoped_user(current_user, payload.location)
    db = get_connection()
    try:
        return create_client_order_record(db, payload, current_user)
    finally:
        db.close()


@router.post("/clients/random", status_code=201)
def create_random_client_order(current_user: dict = Depends(get_current_user)):
    db = get_connection()
    try:
        seed_demo_order_workflows(db)
        if role_name(current_user) == "user":
            part = db.execute(
                """
                SELECT p.id AS part_id, us.location, us.current_stock
                FROM user_stock us
                JOIN parts p ON p.id = us.part_id
                WHERE us.user_id = ? AND us.current_stock > 0
                ORDER BY random()
                LIMIT 1
                """,
                (current_user["id"],),
            ).fetchone()
        else:
            part = db.execute(
                """
                SELECT p.id AS part_id, st.location, st.current_stock
                FROM parts p
                JOIN stock st ON st.part_id = p.id
                WHERE st.current_stock > 0
                ORDER BY random()
                LIMIT 1
                """,
            ).fetchone()
        if part is None:
            raise HTTPException(status_code=409, detail="No stocked parts available for random client order")

        quantity = random.randint(1, max(1, min(6, int(part["current_stock"]))))
        client_name = random.choice(["RRParts Web Client", "Bucharest Auto Service", "Peugeot Fleet Desk"])
        payload = ClientOrderCreatePayload(
            client_name=client_name,
            location=part["location"],
            items=[WorkflowOrderLinePayload(part_id=part["part_id"], quantity=quantity)],
        )
        return create_client_order_record(db, payload, current_user)
    finally:
        db.close()


@router.get("/clients/{order_id}/availability")
def get_client_order_availability(order_id: str, current_user: dict = Depends(get_current_user)):
    db = get_connection()
    try:
        seed_demo_order_workflows(db)
        order = fetch_client_order(db, order_id)
        require_demo_or_owned_order_access(current_user, order)
        return client_order_availability(db, order, current_user)
    finally:
        db.close()


@router.post("/clients/{order_id}/approve")
def approve_client_order(order_id: str, current_user: dict = Depends(get_current_user)):
    db = get_connection()
    try:
        seed_demo_order_workflows(db)
        order = fetch_client_order(db, order_id)
        claim_demo_order_for_user(db, "order_clients", order_id, current_user)
        order = fetch_client_order(db, order_id)
        require_order_record_access(current_user, order)
        if order["status"] not in ("Pending", "Scheduled"):
            raise HTTPException(status_code=400, detail=f"Cannot approve client order in status '{order['status']}'")

        db.execute(
            "UPDATE order_clients SET status = 'Approved', updated_at = ? WHERE id = ?",
            (workflow_utc_now_iso(), order_id),
        )
        try:
            apply_client_order_stock(db, order_id)
        except ValueError as error:
            db.rollback()
            raise HTTPException(status_code=409, detail=str(error)) from error
        create_supplier_replenishments_for_client_shortage(db, order_id)
        db.commit()
        return client_order_to_dict(db, fetch_client_order(db, order_id))
    finally:
        db.close()


@router.post("/clients/{order_id}/deny")
def deny_client_order(order_id: str, current_user: dict = Depends(get_current_user)):
    db = get_connection()
    try:
        seed_demo_order_workflows(db)
        order = fetch_client_order(db, order_id)
        claim_demo_order_for_user(db, "order_clients", order_id, current_user)
        order = fetch_client_order(db, order_id)
        require_order_record_access(current_user, order)
        if order["status"] not in ("Pending", "Scheduled"):
            raise HTTPException(status_code=400, detail=f"Cannot deny client order in status '{order['status']}'")
        if order["stock_applied"]:
            raise HTTPException(status_code=400, detail="Cannot deny a client order after stock was allocated")

        db.execute(
            """
            UPDATE order_clients
            SET status = 'Denied', fulfillment_status = 'denied', updated_at = ?
            WHERE id = ?
            """,
            (workflow_utc_now_iso(), order_id),
        )
        db.commit()
        return client_order_to_dict(db, fetch_client_order(db, order_id))
    finally:
        db.close()


@router.post("/clients/{order_id}/schedule")
def schedule_client_order(
    order_id: str,
    payload: ClientOrderSchedulePayload,
    current_user: dict = Depends(get_current_user),
):
    db = get_connection()
    try:
        seed_demo_order_workflows(db)
        order = fetch_client_order(db, order_id)
        claim_demo_order_for_user(db, "order_clients", order_id, current_user)
        order = fetch_client_order(db, order_id)
        require_order_record_access(current_user, order)
        if order["status"] not in ("Pending", "Scheduled"):
            raise HTTPException(status_code=400, detail=f"Cannot schedule client order in status '{order['status']}'")

        scheduled_for = payload.scheduled_for or parse_clock_time(payload.time)
        db.execute(
            """
            UPDATE order_clients
            SET status = 'Scheduled', scheduled_for = ?, updated_at = ?
            WHERE id = ?
            """,
            (scheduled_for, workflow_utc_now_iso(), order_id),
        )
        db.commit()
        return client_order_to_dict(db, fetch_client_order(db, order_id))
    finally:
        db.close()


@router.post("/clients/{order_id}/complete")
def complete_client_order(order_id: str, current_user: dict = Depends(get_current_user)):
    db = get_connection()
    try:
        seed_demo_order_workflows(db)
        order = fetch_client_order(db, order_id)
        require_order_record_access(current_user, order)
        if order["status"] != "Approved" or order["fulfillment_status"] != "ready" or int(order["shortage_quantity"] or 0) > 0:
            raise HTTPException(status_code=400, detail="Client order is not ready to complete")

        record_client_order_sales(db, order_id)
        db.execute(
            """
            UPDATE order_clients
            SET status = 'Delivered',
                fulfillment_status = 'fulfilled',
                updated_at = ?
            WHERE id = ?
            """,
            (workflow_utc_now_iso(), order_id),
        )
        db.commit()
        return client_order_to_dict(db, fetch_client_order(db, order_id))
    finally:
        db.close()


@router.get("/suppliers")
def list_supplier_orders(
    current_user: dict = Depends(get_current_user),
    status: str | None = Query(None, description="Filter by supplier order status"),
    supplier_id: str | None = Query(None, description="Filter by supplier ID"),
    location: str | None = Query(None, description="Filter by location/location_id"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    db = get_connection()
    try:
        seed_demo_order_workflows(db)
        release_due_supplier_orders(db, current_user)
        query = "SELECT * FROM order_suppliers WHERE 1=1"
        params: list[object] = []

        if status:
            if status not in SUPPLIER_STATUSES:
                raise HTTPException(status_code=422, detail="Invalid supplier order status")
            query += " AND status = ?"
            params.append(status)
        elif role_name(current_user) == "user":
            query += " AND (status IN ('Pending', 'Delayed', 'Received', 'Refused') OR status = 'Delivered')"
        if supplier_id:
            query += " AND supplier_id = ?"
            params.append(supplier_id)
        if location:
            if role_name(current_user) != "user":
                require_order_location_access(current_user, location)
            query += " AND location = ?"
            params.append(location)
        clause, scope_params = include_demo_order_clause(current_user)
        query += clause
        params.extend(scope_params)
        stream_clause, stream_params = user_stream_clause(db, current_user)
        query += stream_clause
        params.extend(stream_params)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = db.execute(query, params).fetchall()
        return [supplier_order_to_dict(db, row) for row in rows]
    finally:
        db.close()


@router.post("/suppliers", status_code=201)
def create_supplier_order(
    payload: SupplierOrderCreatePayload,
    current_user: dict = Depends(get_current_user),
):
    require_payload_location_for_scoped_user(current_user, payload.location)
    db = get_connection()
    try:
        return create_supplier_order_record(db, payload, current_user)
    finally:
        db.close()


@router.post("/suppliers/{order_id}/receive")
def receive_supplier_order(order_id: str, current_user: dict = Depends(get_current_user)):
    db = get_connection()
    try:
        seed_demo_order_workflows(db)
        order = fetch_supplier_order(db, order_id)
        claim_demo_order_for_user(db, "order_suppliers", order_id, current_user)
        order = fetch_supplier_order(db, order_id)
        require_order_record_access(current_user, order)
        if order["status"] in ("Refused",):
            raise HTTPException(status_code=400, detail=f"Cannot receive supplier order in status '{order['status']}'")

        try:
            apply_supplier_order_stock(db, order_id)
        except ValueError as error:
            db.rollback()
            raise HTTPException(status_code=409, detail=str(error)) from error
        db.commit()
        return supplier_order_to_dict(db, fetch_supplier_order(db, order_id))
    finally:
        db.close()


@router.post("/suppliers/{order_id}/postpone")
def postpone_supplier_order(
    order_id: str,
    payload: SupplierOrderPostponePayload,
    current_user: dict = Depends(get_current_user),
):
    db = get_connection()
    try:
        seed_demo_order_workflows(db)
        order = fetch_supplier_order(db, order_id)
        claim_demo_order_for_user(db, "order_suppliers", order_id, current_user)
        order = fetch_supplier_order(db, order_id)
        require_order_record_access(current_user, order)
        if order["status"] in ("Refused", "Received"):
            raise HTTPException(status_code=400, detail=f"Cannot postpone supplier order in status '{order['status']}'")
        if order["stock_applied"]:
            raise HTTPException(status_code=400, detail="Cannot postpone a supplier order after stock was received")

        postponed_until = payload.postponed_until or parse_clock_time(payload.time)
        db.execute(
            """
            UPDATE order_suppliers
            SET status = 'Delayed', postponed_until = ?, estimated_arrival = ?, updated_at = ?
            WHERE id = ?
            """,
            (postponed_until, "Postponed", workflow_utc_now_iso(), order_id),
        )
        db.commit()
        return supplier_order_to_dict(db, fetch_supplier_order(db, order_id))
    finally:
        db.close()


@router.post("/suppliers/{order_id}/refuse")
def refuse_supplier_order(order_id: str, current_user: dict = Depends(get_current_user)):
    db = get_connection()
    try:
        seed_demo_order_workflows(db)
        order = fetch_supplier_order(db, order_id)
        claim_demo_order_for_user(db, "order_suppliers", order_id, current_user)
        order = fetch_supplier_order(db, order_id)
        require_order_record_access(current_user, order)
        if order["stock_applied"]:
            raise HTTPException(status_code=400, detail="Cannot refuse a supplier order after stock was received")

        db.execute(
            "UPDATE order_suppliers SET status = 'Refused', updated_at = ? WHERE id = ?",
            (workflow_utc_now_iso(), order_id),
        )
        db.commit()
        return supplier_order_to_dict(db, fetch_supplier_order(db, order_id))
    finally:
        db.close()



