from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Query

from app.analytics.services.ml_client import safe_ml_service_get, safe_ml_service_post


router = APIRouter(prefix="/ml", tags=["ml"])


def _params(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _result(data: Any, error: str | None) -> dict[str, Any]:
    return {
        "available": error is None,
        "source": "ml-service",
        "data": data if isinstance(data, dict) else {},
        "items": data if isinstance(data, list) else [],
        "error": error,
    }


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    data, error = safe_ml_service_get(path, params=params)
    return _result(data, error)


def _post(
    path: str,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data, error = safe_ml_service_post(path, payload=payload, params=params)
    return _result(data, error)


@router.get("/health")
def ml_health():
    return _get("/health")


@router.get("/model/metadata")
def ml_model_metadata():
    return _get("/model/metadata")


@router.get("/data/locations")
def ml_locations():
    return _get("/data/locations")


@router.get("/data/parts")
def ml_parts():
    return _get("/data/parts")


@router.get("/data/weather")
def ml_weather(
    location: str | None = Query(None, min_length=1),
    start_date: str | None = Query(None, min_length=1),
    end_date: str | None = Query(None, min_length=1),
    limit: int = Query(1000, ge=1, le=20000),
):
    return _get(
        "/data/weather",
        _params(location_id=location, start_date=start_date, end_date=end_date, limit=limit),
    )


@router.get("/data/events")
def ml_events(
    location: str | None = Query(None, min_length=1),
    start_date: str | None = Query(None, min_length=1),
    end_date: str | None = Query(None, min_length=1),
    limit: int = Query(1000, ge=1, le=20000),
):
    return _get(
        "/data/events",
        _params(location_id=location, start_date=start_date, end_date=end_date, limit=limit),
    )


@router.get("/data/sales-history")
def ml_sales_history(
    sku: str | None = Query(None, min_length=1),
    location: str | None = Query(None, min_length=1),
    start_date: str | None = Query(None, min_length=1),
    end_date: str | None = Query(None, min_length=1),
    limit: int = Query(1000, ge=1, le=50000),
):
    return _get(
        "/data/sales-history",
        _params(
            sku=sku,
            location_id=location,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        ),
    )


@router.get("/weather/live")
def ml_live_weather(
    location: str | None = Query(None, min_length=1),
    start_date: str | None = Query(None, min_length=1),
    end_date: str | None = Query(None, min_length=1),
    limit: int = Query(1000, ge=1, le=20000),
    refresh: bool = False,
):
    return _get(
        "/weather/open-meteo",
        _params(
            location_id=location,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            refresh=refresh,
        ),
    )


@router.get("/weather/live/metadata")
def ml_live_weather_metadata():
    return _get("/weather/open-meteo/metadata")


@router.get("/forecast")
def ml_forecast(
    sku: str | None = Query(None, min_length=1),
    location: str | None = Query(None, min_length=1),
    horizon: int = Query(30, ge=1, le=90),
    limit: int = Query(1000, ge=1, le=20000),
):
    return _get(
        "/forecast",
        _params(sku=sku, location_id=location, horizon=horizon, limit=limit),
    )


@router.get("/forecast/{sku}")
def ml_forecast_for_sku(
    sku: str,
    location: str | None = Query(None, min_length=1),
    horizon: int = Query(30, ge=1, le=90),
    limit: int = Query(1000, ge=1, le=20000),
):
    return _get(
        f"/forecast/{sku}",
        _params(location_id=location, horizon=horizon, limit=limit),
    )


@router.get("/segments")
def ml_segments(
    sku: str | None = Query(None, min_length=1),
    location: str | None = Query(None, min_length=1),
    limit: int = Query(1000, ge=1, le=20000),
):
    return _get("/segments", _params(sku=sku, location_id=location, limit=limit))


@router.get("/recommendations")
def ml_recommendations(
    action: str | None = Query(None, min_length=1),
    priority: str | None = Query(None, min_length=1),
    location: str | None = Query(None, min_length=1),
    limit: int = Query(1000, ge=1, le=20000),
):
    return _get(
        "/recommendations",
        _params(action=action, priority=priority, location_id=location, limit=limit),
    )


@router.get("/alerts")
def ml_alerts(
    priority: str | None = Query(None, min_length=1),
    location: str | None = Query(None, min_length=1),
    limit: int = Query(1000, ge=1, le=20000),
):
    return _get("/alerts", _params(priority=priority, location_id=location, limit=limit))


@router.get("/decision/alerts")
def ml_decision_alerts(
    priority: str | None = Query(None, min_length=1),
    status: str | None = Query(None, min_length=1),
    location: str | None = Query(None, min_length=1),
    limit: int = Query(1000, ge=1, le=20000),
):
    return _get(
        "/decision/alerts",
        _params(priority=priority, status=status, location_id=location, limit=limit),
    )


@router.get("/decision/stock-risk")
def ml_decision_stock_risk(
    risk_status: str | None = Query(None, min_length=1),
    location: str | None = Query(None, min_length=1),
    sku: str | None = Query(None, min_length=1),
    limit: int = Query(1000, ge=1, le=20000),
):
    return _get(
        "/decision/stock-risk",
        _params(risk_status=risk_status, location_id=location, sku=sku, limit=limit),
    )


@router.get("/decision/sensitivity-profiles")
def ml_decision_sensitivity_profiles(
    sku: str | None = Query(None, min_length=1),
    location: str | None = Query(None, min_length=1),
    segment: str | None = Query(None, min_length=1),
    limit: int = Query(1000, ge=1, le=20000),
):
    return _get(
        "/decision/sensitivity-profiles",
        _params(sku=sku, location_id=location, segment=segment, limit=limit),
    )


@router.get("/decision/scenarios")
def ml_decision_scenarios(
    sku: str | None = Query(None, min_length=1),
    location: str | None = Query(None, min_length=1),
    limit: int = Query(1000, ge=1, le=20000),
):
    return _get("/decision/scenarios", _params(sku=sku, location_id=location, limit=limit))


@router.get("/decision/map")
def ml_decision_map(
    location: str | None = Query(None, min_length=1),
    limit: int = Query(1000, ge=1, le=20000),
):
    return _get("/decision/map", _params(location_id=location, limit=limit))


@router.get("/decision/explainability")
def ml_decision_explainability(
    alert_id: str | None = Query(None, min_length=1),
    sku: str | None = Query(None, min_length=1),
    location: str | None = Query(None, min_length=1),
    limit: int = Query(1000, ge=1, le=20000),
):
    return _get(
        "/decision/explainability",
        _params(alert_id=alert_id, sku=sku, location_id=location, limit=limit),
    )


@router.get("/decision/model-monitoring")
def ml_decision_model_monitoring():
    return _get("/decision/model-monitoring")


@router.get("/decision/integrations")
def ml_decision_integrations():
    return _get("/decision/integrations")


@router.get("/kpis")
def ml_kpis(horizon: int = Query(30, ge=1, le=90)):
    return _get("/kpis", _params(horizon=horizon))


@router.post("/decision/build")
def ml_build_decision_layer(horizon: int = Query(21, ge=1, le=90)):
    return _post("/decision/build", params=_params(horizon=horizon))


@router.post("/refresh-outputs")
def ml_refresh_outputs(payload: dict[str, Any] | None = Body(default=None)):
    return _post("/refresh-outputs", payload=payload or {})


@router.post("/retrain")
def ml_retrain(payload: dict[str, Any] | None = Body(default=None)):
    return _post("/retrain", payload=payload or {})
