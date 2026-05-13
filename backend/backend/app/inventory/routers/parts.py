from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_admin, require_authenticated_user
from app.db import get_connection
from app.inventory.schemas.parts import PartCreatePayload, PartUpdatePayload
from app.inventory.services.parts_catalog import (
    get_catalog_filters,
    get_catalog_part,
    list_catalog_parts,
)


router = APIRouter()


@router.get("/parts")
def get_parts(current_user: dict = Depends(require_authenticated_user)):
    connection = get_connection()
    cursor = connection.cursor()

    role = current_user.get("role_name", current_user.get("role", "user"))
    user_location_ids = current_user.get("user_location_ids", [])
    user_locations = current_user.get("user_locations", [])

    query = """
    SELECT
        p.id,
        p.sku,
        p.part_name,
        p.category,
        p.seasonality_profile,
        p.base_demand,
        p.supplier_id,
        s.supplier_name AS supplier,
        p.unit_price,
        p.salary_sensitivity,
        p.lead_time_days,
        p.min_order_qty,
        p.criticality
    FROM parts p
    LEFT JOIN suppliers s ON s.id = p.supplier_id
    """

    params = []
    if role == "user":
        scope_values = user_location_ids or user_locations
        if not scope_values:
            connection.close()
            return []
        placeholders = ", ".join(["?"] * len(scope_values))
        scope_column = "st.location_id" if user_location_ids else "st.location"
        query += f" WHERE EXISTS (SELECT 1 FROM stock st WHERE st.part_id = p.id AND {scope_column} IN ({placeholders}))"
        params.extend(scope_values)

    query += " ORDER BY p.id"
    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    connection.close()
    return rows


@router.get("/parts/catalog")
def get_parts_catalog(
    search: str | None = Query(default=None, min_length=1),
    category: str | None = Query(default=None, min_length=1),
    supplier: str | None = Query(default=None, min_length=1),
    status: str | None = Query(default=None, min_length=1),
    availability: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(require_authenticated_user),
):
    connection = get_connection()
    try:
        return list_catalog_parts(
            connection,
            current_user,
            search=search,
            category=category,
            supplier=supplier,
            status=status,
            availability=availability,
            limit=limit,
            offset=offset,
        )
    finally:
        connection.close()


@router.get("/parts/catalog/filters")
def get_parts_catalog_filters(current_user: dict = Depends(require_authenticated_user)):
    connection = get_connection()
    try:
        return get_catalog_filters(connection, current_user)
    finally:
        connection.close()


@router.get("/parts/catalog/{part_id}")
def get_parts_catalog_item(part_id: int, current_user: dict = Depends(require_authenticated_user)):
    connection = get_connection()
    try:
        item = get_catalog_part(connection, current_user, part_id)
    finally:
        connection.close()

    if item is None:
        raise HTTPException(status_code=404, detail="Part not found")

    return item


@router.get("/parts/{part_id}")
def get_part(part_id: int, current_user: dict = Depends(require_authenticated_user)):
    connection = get_connection()
    cursor = connection.cursor()

    role = current_user.get("role_name", current_user.get("role", "user"))
    user_location_ids = current_user.get("user_location_ids", [])
    user_locations = current_user.get("user_locations", [])

    query = """
    SELECT
        p.id,
        p.sku,
        p.part_name,
        p.category,
        p.seasonality_profile,
        p.base_demand,
        p.supplier_id,
        s.supplier_name AS supplier,
        p.unit_price,
        p.salary_sensitivity,
        p.lead_time_days,
        p.min_order_qty,
        p.criticality
    FROM parts p
    LEFT JOIN suppliers s ON s.id = p.supplier_id
    WHERE p.id = ?
    """
    params = [part_id]

    if role == "user":
        scope_values = user_location_ids or user_locations
        if not scope_values:
            connection.close()
            raise HTTPException(status_code=404, detail="Part not found")
        placeholders = ", ".join(["?"] * len(scope_values))
        scope_column = "st.location_id" if user_location_ids else "st.location"
        query += f" AND EXISTS (SELECT 1 FROM stock st WHERE st.part_id = p.id AND {scope_column} IN ({placeholders}))"
        params.extend(scope_values)

    cursor.execute(query, params)

    row = cursor.fetchone()
    connection.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Part not found")

    return dict(row)


@router.post("/parts")
def create_part(payload: PartCreatePayload, _: dict = Depends(require_admin)):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("SELECT id FROM suppliers WHERE id = ?", (payload.supplier_id,))
        if cursor.fetchone() is None:
            connection.close()
            raise HTTPException(status_code=400, detail="Invalid supplier_id")

        cursor.execute(
            """
            INSERT INTO parts (
                sku, part_name, category, seasonality_profile, base_demand,
                supplier_id, unit_price, salary_sensitivity, lead_time_days,
                min_order_qty, criticality
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.sku,
                payload.part_name,
                payload.category,
                payload.seasonality_profile,
                payload.base_demand,
                payload.supplier_id,
                payload.unit_price,
                payload.salary_sensitivity,
                payload.lead_time_days,
                payload.min_order_qty,
                payload.criticality,
            ),
        )
        connection.commit()
        new_part_id = cursor.lastrowid
        connection.close()
        return {"id": new_part_id, "message": "Part created"}
    except Exception as error:
        connection.close()
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.patch("/parts/{part_id}")
def update_part(part_id: int, payload: PartUpdatePayload, _: dict = Depends(require_admin)):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT id FROM parts WHERE id = ?", (part_id,))
    if cursor.fetchone() is None:
        connection.close()
        raise HTTPException(status_code=404, detail="Part not found")

    try:
        updates = []
        values = []

        if payload.sku is not None:
            updates.append("sku = ?")
            values.append(payload.sku)
        if payload.part_name is not None:
            updates.append("part_name = ?")
            values.append(payload.part_name)
        if payload.category is not None:
            updates.append("category = ?")
            values.append(payload.category)
        if payload.seasonality_profile is not None:
            updates.append("seasonality_profile = ?")
            values.append(payload.seasonality_profile)
        if payload.base_demand is not None:
            updates.append("base_demand = ?")
            values.append(payload.base_demand)
        if payload.supplier_id is not None:
            cursor.execute("SELECT id FROM suppliers WHERE id = ?", (payload.supplier_id,))
            if cursor.fetchone() is None:
                connection.close()
                raise HTTPException(status_code=400, detail="Invalid supplier_id")
            updates.append("supplier_id = ?")
            values.append(payload.supplier_id)
        if payload.unit_price is not None:
            updates.append("unit_price = ?")
            values.append(payload.unit_price)
        if payload.salary_sensitivity is not None:
            updates.append("salary_sensitivity = ?")
            values.append(payload.salary_sensitivity)
        if payload.lead_time_days is not None:
            updates.append("lead_time_days = ?")
            values.append(payload.lead_time_days)
        if payload.min_order_qty is not None:
            updates.append("min_order_qty = ?")
            values.append(payload.min_order_qty)
        if payload.criticality is not None:
            updates.append("criticality = ?")
            values.append(payload.criticality)

        if not updates:
            connection.close()
            raise HTTPException(status_code=400, detail="No fields to update")

        values.append(part_id)
        query = f"UPDATE parts SET {', '.join(updates)} WHERE id = ?"

        cursor.execute(query, values)
        connection.commit()
        connection.close()
        return {"message": "Part updated"}
    except Exception as error:
        connection.close()
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.delete("/parts/{part_id}")
def delete_part(part_id: int, _: dict = Depends(require_admin)):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT id FROM parts WHERE id = ?", (part_id,))
    if cursor.fetchone() is None:
        connection.close()
        raise HTTPException(status_code=404, detail="Part not found")

    try:
        cursor.execute("DELETE FROM parts WHERE id = ?", (part_id,))
        connection.commit()
        connection.close()
        return {"message": "Part deleted"}
    except Exception as error:
        connection.close()
        raise HTTPException(status_code=400, detail=str(error)) from error

