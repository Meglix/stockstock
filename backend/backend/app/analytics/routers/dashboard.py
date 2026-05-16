from fastapi import APIRouter, Depends, Query

from app.analytics.services.dashboard import (
    get_dashboard_summary,
    get_market_trends,
    get_priority_stock,
    get_sales_flow,
    get_supplier_map,
)
from app.analytics.services.ml_client import (
    build_mock_forecast_rows,
    forecast_source_horizon,
    normalize_forecast_rows,
    read_forecast_csv,
    resolved_location_id,
    safe_ml_service_get,
)
from app.core.auth import require_authenticated_user
from app.db import get_connection


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(current_user: dict = Depends(require_authenticated_user)):
    connection = get_connection()
    try:
        return get_dashboard_summary(connection, current_user)
    finally:
        connection.close()


@router.get("/sales-flow")
def dashboard_sales_flow(
    current_user: dict = Depends(require_authenticated_user),
    months: int = Query(6, ge=1, le=12),
    categories: int = Query(6, ge=1, le=12),
    category: str | None = Query(None, min_length=1),
    location: str | None = Query(None, min_length=1, description="Optional city or location_id filter"),
):
    connection = get_connection()
    try:
        return get_sales_flow(
            connection,
            current_user,
            months_count=months,
            category_limit=categories,
            selected_category=category,
            requested_location=location,
        )
    finally:
        connection.close()


@router.get("/market-trends")
def dashboard_market_trends(
    current_user: dict = Depends(require_authenticated_user),
    limit: int = Query(5, ge=1, le=20),
    location: str | None = Query(None, min_length=1, description="Optional city or location_id filter"),
):
    connection = get_connection()
    try:
        return get_market_trends(connection, current_user, limit=limit, requested_location=location)
    finally:
        connection.close()


@router.get("/supplier-locations")
def dashboard_supplier_locations(
    current_user: dict = Depends(require_authenticated_user),
    limit: int = Query(8, ge=1, le=20),
):
    connection = get_connection()
    try:
        return get_supplier_map(connection, current_user, limit=limit)
    finally:
        connection.close()


@router.get("/priority-stock")
def dashboard_priority_stock(
    current_user: dict = Depends(require_authenticated_user),
    limit: int = Query(5, ge=1, le=20),
):
    connection = get_connection()
    try:
        return get_priority_stock(connection, current_user, limit=limit)
    finally:
        connection.close()


@router.get("/ml/forecast")
def dashboard_ml_forecast(
    current_user: dict = Depends(require_authenticated_user),
    sku: str | None = Query(None, min_length=1),
    location: str | None = Query(None, min_length=1, description="Optional location_id override"),
    horizon: int = Query(30, ge=1, le=90),
    limit: int = Query(200, ge=1, le=2000),
):
    location_id = resolved_location_id(current_user, location)
    source_horizon = forecast_source_horizon(horizon)
    items, error = safe_ml_service_get(
        "/forecast",
        params={
            "sku": sku,
            "location_id": location_id,
            "horizon": source_horizon,
            "limit": limit,
        },
    )
    normalized_items = normalize_forecast_rows(
        items,
        requested_sku=sku,
        requested_location=location_id,
        requested_horizon=horizon,
        limit=limit,
    )
    if normalized_items:
        return {
            "available": True,
            "source": "ml-service",
            "location_id": location_id,
            "requested_horizon": horizon,
            "source_horizon": source_horizon,
            "items": normalized_items,
            "error": None,
        }

    csv_items, csv_error = read_forecast_csv(
        sku=sku,
        location_id=location_id,
        requested_horizon=horizon,
        source_horizon=source_horizon,
        limit=limit,
    )
    if csv_items:
        return {
            "available": True,
            "source": "ml-csv-fallback",
            "location_id": location_id,
            "requested_horizon": horizon,
            "source_horizon": source_horizon,
            "items": csv_items,
            "error": f"ML service unavailable or empty: {error}" if error else "ML service returned no matching forecast rows.",
        }

    fallback_error = error or csv_error or "No ML forecast rows matched the request."
    return {
        "available": False,
        "source": "mock-fallback",
        "location_id": location_id,
        "requested_horizon": horizon,
        "source_horizon": source_horizon,
        "items": build_mock_forecast_rows(sku=sku, location_id=location_id, horizon=horizon, limit=limit),
        "error": fallback_error,
    }


@router.get("/ml/recommendations")
def dashboard_ml_recommendations(
    current_user: dict = Depends(require_authenticated_user),
    action: str | None = Query(None, min_length=1),
    priority: str | None = Query(None, min_length=1),
    location: str | None = Query(None, min_length=1, description="Optional location_id override"),
    limit: int = Query(200, ge=1, le=2000),
):
    location_id = resolved_location_id(current_user, location)
    items, error = safe_ml_service_get(
        "/recommendations",
        params={
            "action": action,
            "priority": priority,
            "location_id": location_id,
            "limit": limit,
        },
    )
    return {
        "available": error is None,
        "source": "ml-service",
        "location_id": location_id,
        "items": items if isinstance(items, list) else [],
        "error": error,
    }


@router.get("/ml/alerts")
def dashboard_ml_alerts(
    current_user: dict = Depends(require_authenticated_user),
    priority: str | None = Query(None, min_length=1),
    location: str | None = Query(None, min_length=1, description="Optional location_id override"),
    limit: int = Query(200, ge=1, le=2000),
):
    location_id = resolved_location_id(current_user, location)
    items, error = safe_ml_service_get(
        "/decision/alerts",
        params={
            "priority": priority,
            "location_id": location_id,
            "limit": limit,
        },
    )
    return {
        "available": error is None,
        "source": "ml-service",
        "location_id": location_id,
        "items": items if isinstance(items, list) else [],
        "error": error,
    }


@router.get("/ml/kpis")
def dashboard_ml_kpis(
    current_user: dict = Depends(require_authenticated_user),
    horizon: int = Query(30, ge=1, le=90),
):
    location_id = resolved_location_id(current_user)
    data, error = safe_ml_service_get(
        "/kpis",
        params={"horizon": horizon},
    )
    return {
        "available": error is None,
        "source": "ml-service",
        "location_id": location_id,
        "data": data if isinstance(data, dict) else {},
        "error": error,
    }
