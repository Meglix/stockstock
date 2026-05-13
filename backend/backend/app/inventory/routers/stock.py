from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_authenticated_user
from app.db import get_connection
from app.inventory.schemas.stock import StockCreatePayload, StockUpdatePayload
from app.inventory.services.user_stock import (
    delete_user_stock,
    get_user_stock_item,
    is_user,
    list_user_stock,
    patch_user_stock,
    upsert_user_stock,
)


router = APIRouter()


@router.get("/stock")
def get_stock(current_user: dict = Depends(require_authenticated_user)):
    connection = get_connection()
    cursor = connection.cursor()

    if is_user(current_user):
        user_rows = list_user_stock(connection, current_user)
        if user_rows:
            connection.close()
            return user_rows

    role = current_user.get("role_name", current_user.get("role", "user"))
    user_location_ids = current_user.get("user_location_ids", [])
    user_locations = current_user.get("user_locations", [])

    query = """
    SELECT
        st.part_id,
        p.sku,
        p.part_name,
        p.category,
        p.min_order_qty AS part_min_order_qty,
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
        st.stockout_days_history,
        st.total_sales_history,
        st.latent_demand_signal_history,
        st.inventory_status,
        st.avg_daily_demand_30d,
        st.last_updated,
        CASE
            WHEN st.current_stock <= st.reorder_point THEN 1
            ELSE 0
        END AS below_reorder_point,
        st.optimal_stock - st.current_stock AS stock_gap
    FROM stock st
    JOIN parts p ON p.id = st.part_id
    """

    params = []
    if role == "user":
        scope_values = user_location_ids or user_locations
        if not scope_values:
            connection.close()
            return []
        placeholders = ", ".join(["?"] * len(scope_values))
        scope_column = "st.location_id" if user_location_ids else "st.location"
        query += f" WHERE {scope_column} IN ({placeholders})"
        params.extend(scope_values)

    query += " ORDER BY p.sku, st.location"

    cursor.execute(query, params)

    rows = cursor.fetchall()
    stock_list = []
    for row in rows:
        stock_list.append(dict(row))

    connection.close()
    return stock_list


@router.get("/stock/{part_id}")
def get_stock_for_part(part_id: int, current_user: dict = Depends(require_authenticated_user)):
    connection = get_connection()
    cursor = connection.cursor()

    if is_user(current_user):
        item = get_user_stock_item(connection, current_user, part_id)
        if item is not None:
            connection.close()
            return [item]

    role = current_user.get("role_name", current_user.get("role", "user"))
    user_location_ids = current_user.get("user_location_ids", [])
    user_locations = current_user.get("user_locations", [])

    cursor.execute("SELECT id FROM parts WHERE id = ?", (part_id,))
    if cursor.fetchone() is None:
        connection.close()
        raise HTTPException(status_code=404, detail="Part not found")

    query = """
    SELECT
        st.part_id,
        p.sku,
        p.part_name,
        p.category,
        p.min_order_qty AS part_min_order_qty,
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
        st.stockout_days_history,
        st.total_sales_history,
        st.latent_demand_signal_history,
        st.inventory_status,
        st.avg_daily_demand_30d,
        st.last_updated,
        CASE
            WHEN st.current_stock <= st.reorder_point THEN 1
            ELSE 0
        END AS below_reorder_point,
        st.optimal_stock - st.current_stock AS stock_gap
    FROM stock st
    JOIN parts p ON p.id = st.part_id
    WHERE st.part_id = ?
    """
    params = [part_id]

    if role == "user":
        scope_values = user_location_ids or user_locations
        if not scope_values:
            connection.close()
            raise HTTPException(status_code=404, detail="No stock records found for this part")
        placeholders = ", ".join(["?"] * len(scope_values))
        scope_column = "st.location_id" if user_location_ids else "st.location"
        query += f" AND {scope_column} IN ({placeholders})"
        params.extend(scope_values)

    query += " ORDER BY st.location"
    cursor.execute(query, params)

    rows = cursor.fetchall()
    stock_list = []
    for row in rows:
        stock_list.append(dict(row))

    connection.close()

    if not stock_list:
        if is_user(current_user):
            raise HTTPException(status_code=404, detail="No user stock record found for this part")
        raise HTTPException(status_code=404, detail="No stock records found for this part")

    return stock_list


@router.post("/stock")
def create_stock(payload: StockCreatePayload, current_user: dict = Depends(require_authenticated_user)):
    connection = get_connection()
    cursor = connection.cursor()

    if is_user(current_user):
        try:
            return upsert_user_stock(connection, current_user, payload)
        finally:
            connection.close()

    cursor.execute("SELECT id FROM parts WHERE id = ?", (payload.part_id,))
    if cursor.fetchone() is None:
        connection.close()
        raise HTTPException(status_code=404, detail="Part not found")

    cursor.execute(
        "SELECT part_id FROM stock WHERE part_id = ? AND location = ?",
        (payload.part_id, payload.location),
    )
    if cursor.fetchone() is not None:
        connection.close()
        raise HTTPException(status_code=409, detail="Stock record already exists")

    if payload.optimal_stock < payload.safety_stock:
        connection.close()
        raise HTTPException(status_code=400, detail="optimal_stock must be >= safety_stock")

    try:
        cursor.execute(
            """
            INSERT INTO stock (
                part_id, location, location_id, city, country_code,
                current_stock, reorder_point, safety_stock, optimal_stock,
                min_order_qty, lead_time_days, pending_order_qty,
                stockout_days_history, total_sales_history,
                latent_demand_signal_history, inventory_status,
                avg_daily_demand_30d, last_updated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.part_id,
                payload.location,
                payload.location_id,
                payload.city,
                payload.country_code,
                payload.current_stock,
                payload.reorder_point,
                payload.safety_stock,
                payload.optimal_stock,
                payload.min_order_qty,
                payload.lead_time_days,
                payload.pending_order_qty,
                payload.stockout_days_history,
                payload.total_sales_history,
                payload.latent_demand_signal_history,
                payload.inventory_status,
                payload.avg_daily_demand_30d,
                datetime.now().isoformat(),
            ),
        )
        connection.commit()
        connection.close()
        return {"message": "Stock record created"}
    except Exception as error:
        connection.close()
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.patch("/stock/{part_id}/{location}")
def update_stock(
    part_id: int,
    location: str,
    payload: StockUpdatePayload,
    current_user: dict = Depends(require_authenticated_user),
):
    connection = get_connection()
    cursor = connection.cursor()

    if is_user(current_user):
        try:
            return patch_user_stock(connection, current_user, part_id, payload)
        finally:
            connection.close()

    cursor.execute(
        "SELECT part_id FROM stock WHERE part_id = ? AND (location = ? OR location_id = ?)",
        (part_id, location, location),
    )
    if cursor.fetchone() is None:
        connection.close()
        raise HTTPException(status_code=404, detail="Stock record not found")

    try:
        updates = []
        values = []

        if payload.current_stock is not None:
            updates.append("current_stock = ?")
            values.append(payload.current_stock)
        if payload.reorder_point is not None:
            updates.append("reorder_point = ?")
            values.append(payload.reorder_point)
        if payload.safety_stock is not None:
            updates.append("safety_stock = ?")
            values.append(payload.safety_stock)
        if payload.optimal_stock is not None:
            updates.append("optimal_stock = ?")
            values.append(payload.optimal_stock)
        if payload.min_order_qty is not None:
            updates.append("min_order_qty = ?")
            values.append(payload.min_order_qty)
        if payload.lead_time_days is not None:
            updates.append("lead_time_days = ?")
            values.append(payload.lead_time_days)
        if payload.pending_order_qty is not None:
            updates.append("pending_order_qty = ?")
            values.append(payload.pending_order_qty)
        if payload.stockout_days_history is not None:
            updates.append("stockout_days_history = ?")
            values.append(payload.stockout_days_history)
        if payload.total_sales_history is not None:
            updates.append("total_sales_history = ?")
            values.append(payload.total_sales_history)
        if payload.latent_demand_signal_history is not None:
            updates.append("latent_demand_signal_history = ?")
            values.append(payload.latent_demand_signal_history)
        if payload.inventory_status is not None:
            updates.append("inventory_status = ?")
            values.append(payload.inventory_status)
        if payload.avg_daily_demand_30d is not None:
            updates.append("avg_daily_demand_30d = ?")
            values.append(payload.avg_daily_demand_30d)

        if (
            payload.optimal_stock is not None
            and payload.safety_stock is not None
            and payload.optimal_stock < payload.safety_stock
        ):
            connection.close()
            raise HTTPException(status_code=400, detail="optimal_stock must be >= safety_stock")

        if not updates:
            connection.close()
            raise HTTPException(status_code=400, detail="No fields to update")

        updates.append("last_updated = ?")
        values.append(datetime.now().isoformat())
        values.extend([part_id, location, location])

        query = f"UPDATE stock SET {', '.join(updates)} WHERE part_id = ? AND (location = ? OR location_id = ?)"

        cursor.execute(query, values)
        connection.commit()
        connection.close()
        return {"message": "Stock updated"}
    except Exception as error:
        connection.close()
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.delete("/stock/{part_id}/{location}")
def delete_stock(
    part_id: int,
    location: str,
    current_user: dict = Depends(require_authenticated_user),
):
    connection = get_connection()
    cursor = connection.cursor()

    if is_user(current_user):
        try:
            delete_user_stock(connection, current_user, part_id)
            return {"message": "User stock record deleted"}
        finally:
            connection.close()

    cursor.execute(
        "SELECT part_id FROM stock WHERE part_id = ? AND (location = ? OR location_id = ?)",
        (part_id, location, location),
    )
    if cursor.fetchone() is None:
        connection.close()
        raise HTTPException(status_code=404, detail="Stock record not found")

    try:
        cursor.execute(
            "DELETE FROM stock WHERE part_id = ? AND (location = ? OR location_id = ?)",
            (part_id, location, location),
        )
        connection.commit()
        connection.close()
        return {"message": "Stock record deleted"}
    except Exception as error:
        connection.close()
        raise HTTPException(status_code=400, detail=str(error)) from error
