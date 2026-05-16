from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import API_TITLE, API_VERSION, DATA_PROCESSED_DIR, DATA_RAW_DIR, DEFAULT_FORECAST_HORIZON, MODEL_DIR
from app.schemas import RefreshRequest, RetrainRequest
from ml.cluster import train_cluster_model
from ml.data_generator import generate_dataset
from ml.decision_layer import generate_decision_layer
from ml.forecast import run_forecast
from ml.recommend import generate_recommendations
from ml.train import train_forecast_model

app = FastAPI(title=API_TITLE, version=API_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Fisier lipsa: {path.name}")
    return pd.read_csv(path)


def _records(df: pd.DataFrame):
    return json.loads(df.replace({float("nan"): None}).to_json(orient="records"))


def _filter_common(df: pd.DataFrame, sku: Optional[str] = None, location_id: Optional[str] = None, limit: int = 1000) -> pd.DataFrame:
    result = df.copy()
    if sku:
        result = result[result["sku"].astype(str).str.upper() == sku.upper()]
    if location_id:
        result = result[result["location_id"].astype(str).str.upper() == location_id.upper()]
    return result.head(limit)


def _read_forecast_for_horizon(horizon: int) -> pd.DataFrame:
    exact_path = DATA_PROCESSED_DIR / f"forecast_{horizon}d.csv"
    if exact_path.exists():
        return _read_csv(exact_path)

    default_path = DATA_PROCESSED_DIR / f"forecast_{DEFAULT_FORECAST_HORIZON}d.csv"
    if horizon <= DEFAULT_FORECAST_HORIZON and default_path.exists():
        df = _read_csv(default_path)
        if "horizon_day" in df.columns:
            horizon_days = pd.to_numeric(df["horizon_day"], errors="coerce")
            df = df[horizon_days <= horizon]
        elif "forecast_date" in df.columns:
            df = df.sort_values("forecast_date").groupby(["sku", "location_id"], as_index=False).head(horizon)
        return df

    raise HTTPException(status_code=404, detail=f"Fisier lipsa: {exact_path.name}")


@app.get("/health")
def health():
    required = {
        "sales_history": DATA_RAW_DIR / "sales_history.csv",
        "weather_daily": DATA_RAW_DIR / "weather_daily.csv",
        "calendar_daily": DATA_RAW_DIR / "calendar_daily.csv",
        "forecast_model": MODEL_DIR / "demand_forecast_model.joblib",
        "cluster_model": MODEL_DIR / "demand_segment_kmeans.joblib",
        "forecast_30d": DATA_PROCESSED_DIR / f"forecast_{DEFAULT_FORECAST_HORIZON}d.csv",
        "recommendations": DATA_PROCESSED_DIR / "recommendations.csv",
        "decision_layer": DATA_PROCESSED_DIR / "decision_layer" / "decision_layer_manifest.json",
    }
    return {"status": "ok", "files": {name: path.exists() for name, path in required.items()}}


@app.get("/model/metadata")
def model_metadata():
    forecast_meta = MODEL_DIR / "metadata.json"
    cluster_meta = MODEL_DIR / "cluster_metadata.json"
    result = {}
    if forecast_meta.exists():
        result["forecast"] = json.loads(forecast_meta.read_text(encoding="utf-8"))
    if cluster_meta.exists():
        result["clustering"] = json.loads(cluster_meta.read_text(encoding="utf-8"))
    return result


@app.get("/data/locations")
def locations():
    return _records(_read_csv(DATA_RAW_DIR / "eu_locations.csv"))


@app.get("/data/parts")
def parts():
    return _records(_read_csv(DATA_RAW_DIR / "parts_master.csv"))


@app.get("/data/weather")
def weather(
    location_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(1000, le=20000),
):
    df = _read_csv(DATA_RAW_DIR / "weather_daily.csv")
    if location_id:
        df = df[df["location_id"].str.upper() == location_id.upper()]
    if start_date:
        df = df[df["date"] >= start_date]
    if end_date:
        df = df[df["date"] <= end_date]
    return _records(df.head(limit))


@app.get("/data/sales-history")
def sales_history(
    sku: Optional[str] = None,
    location_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(1000, le=50000),
):
    df = _read_csv(DATA_RAW_DIR / "sales_history.csv")
    if sku:
        df = df[df["sku"].astype(str).str.upper() == sku.upper()]
    if location_id:
        df = df[df["location_id"].astype(str).str.upper() == location_id.upper()]
    if start_date:
        df = df[df["date"] >= start_date]
    if end_date:
        df = df[df["date"] <= end_date]
    df = df.sort_values("date")
    limited = df.head(limit) if start_date or end_date else df.tail(limit)
    return _records(limited.sort_values("date"))


@app.get("/data/events")
def events(
    location_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(1000, le=20000),
):
    df = _read_csv(DATA_RAW_DIR / "calendar_events.csv")
    if location_id:
        df = df[df["location_id"].str.upper() == location_id.upper()]
    if start_date:
        df = df[df["date"] >= start_date]
    if end_date:
        df = df[df["date"] <= end_date]
    return _records(df.head(limit))


@app.get("/weather/open-meteo")
def open_meteo_weather(
    location_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(1000, le=20000),
    refresh: bool = False,
):
    df = _read_csv(DATA_RAW_DIR / "weather_forecast_open_meteo.csv")
    if location_id:
        df = df[df["location_id"].astype(str).str.upper() == location_id.upper()]
    if start_date:
        df = df[df["date"] >= start_date]
    if end_date:
        df = df[df["date"] <= end_date]
    return _records(df.sort_values("date").head(limit))


@app.get("/weather/open-meteo/metadata")
def open_meteo_weather_metadata():
    path = DATA_RAW_DIR / "weather_forecast_open_meteo_metadata.json"
    if not path.exists():
        return {"available": False}
    return {"available": True, **json.loads(path.read_text(encoding="utf-8"))}


@app.get("/forecast")
def forecast(
    sku: Optional[str] = None,
    location_id: Optional[str] = None,
    horizon: int = DEFAULT_FORECAST_HORIZON,
    limit: int = Query(1000, le=20000),
):
    df = _read_forecast_for_horizon(horizon)
    return _records(_filter_common(df, sku=sku, location_id=location_id, limit=limit))


@app.get("/forecast/{sku}")
def forecast_for_sku(
    sku: str,
    location_id: Optional[str] = None,
    horizon: int = DEFAULT_FORECAST_HORIZON,
    limit: int = Query(1000, le=20000),
):
    df = _read_forecast_for_horizon(horizon)
    return _records(_filter_common(df, sku=sku, location_id=location_id, limit=limit))


@app.get("/segments")
def segments(sku: Optional[str] = None, location_id: Optional[str] = None, limit: int = Query(1000, le=20000)):
    df = _read_csv(DATA_PROCESSED_DIR / "segments_kmeans.csv")
    return _records(_filter_common(df, sku=sku, location_id=location_id, limit=limit))


@app.get("/recommendations")
def recommendations(
    action: Optional[str] = None,
    priority: Optional[str] = None,
    location_id: Optional[str] = None,
    limit: int = Query(1000, le=20000),
):
    df = _read_csv(DATA_PROCESSED_DIR / "recommendations.csv")
    if action:
        df = df[df["recommended_action"].str.lower() == action.lower()]
    if priority:
        df = df[df["priority"].str.lower() == priority.lower()]
    if location_id:
        df = df[df["location_id"].str.upper() == location_id.upper()]
    return _records(df.head(limit))


@app.get("/alerts")
def alerts(priority: Optional[str] = None, location_id: Optional[str] = None, limit: int = Query(1000, le=20000)):
    df = _read_csv(DATA_PROCESSED_DIR / "alerts.csv")
    if priority and "priority" in df.columns:
        df = df[df["priority"].str.lower() == priority.lower()]
    if location_id and "location_id" in df.columns:
        df = df[df["location_id"].str.upper() == location_id.upper()]
    return _records(df.head(limit))


@app.get("/decision/alerts")
def decision_alerts(
    priority: Optional[str] = None,
    status: Optional[str] = None,
    location_id: Optional[str] = None,
    limit: int = Query(1000, le=20000),
):
    df = _read_csv(DATA_PROCESSED_DIR / "decision_layer" / "dealer_alert_center.csv")
    if priority and "priority" in df.columns:
        df = df[df["priority"].str.lower() == priority.lower()]
    if status and "status" in df.columns:
        df = df[df["status"].str.lower() == status.lower()]
    if location_id and "location_id" in df.columns:
        df = df[df["location_id"].str.upper() == location_id.upper()]
    return _records(df.head(limit))


@app.get("/decision/stock-risk")
def decision_stock_risk(
    risk_status: Optional[str] = None,
    location_id: Optional[str] = None,
    sku: Optional[str] = None,
    limit: int = Query(1000, le=20000),
):
    df = _read_csv(DATA_PROCESSED_DIR / "decision_layer" / "stock_risk_reorder_engine.csv")
    if risk_status and "risk_status" in df.columns:
        df = df[df["risk_status"].str.lower() == risk_status.lower()]
    return _records(_filter_common(df, sku=sku, location_id=location_id, limit=limit))


@app.get("/decision/sensitivity-profiles")
def decision_sensitivity_profiles(
    sku: Optional[str] = None,
    location_id: Optional[str] = None,
    segment: Optional[str] = None,
    limit: int = Query(1000, le=20000),
):
    df = _read_csv(DATA_PROCESSED_DIR / "decision_layer" / "product_sensitivity_profiles.csv")
    if segment and "sensitivity_segment" in df.columns:
        df = df[df["sensitivity_segment"].str.lower() == segment.lower()]
    return _records(_filter_common(df, sku=sku, location_id=location_id, limit=limit))


@app.get("/decision/scenarios")
def decision_scenarios(
    sku: Optional[str] = None,
    location_id: Optional[str] = None,
    limit: int = Query(1000, le=20000),
):
    df = _read_csv(DATA_PROCESSED_DIR / "decision_layer" / "forecast_scenarios_21d.csv")
    return _records(_filter_common(df, sku=sku, location_id=location_id, limit=limit))


@app.get("/decision/map")
def decision_map(location_id: Optional[str] = None, limit: int = Query(1000, le=20000)):
    df = _read_csv(DATA_PROCESSED_DIR / "decision_layer" / "dealer_risk_map.csv")
    if location_id and "location_id" in df.columns:
        df = df[df["location_id"].str.upper() == location_id.upper()]
    return _records(df.head(limit))


@app.get("/decision/explainability")
def decision_explainability(
    alert_id: Optional[str] = None,
    sku: Optional[str] = None,
    location_id: Optional[str] = None,
    limit: int = Query(1000, le=20000),
):
    df = _read_csv(DATA_PROCESSED_DIR / "decision_layer" / "model_explainability.csv")
    if alert_id and "alert_id" in df.columns:
        df = df[df["alert_id"].str.upper() == alert_id.upper()]
    return _records(_filter_common(df, sku=sku, location_id=location_id, limit=limit))


@app.get("/decision/model-monitoring")
def decision_model_monitoring():
    base = DATA_PROCESSED_DIR / "decision_layer"
    summary_path = base / "model_monitoring_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    return {
        "summary": summary,
        "by_category": _records(_read_csv(base / "model_monitoring_by_category.csv")),
        "segmented_daily": _records(_read_csv(base / "segmented_daily_metrics.csv")),
        "segmented_21d": _records(_read_csv(base / "segmented_21d_metrics.csv")),
        "business_alert_backtest_21d": _records(_read_csv(base / "business_alert_backtest_21d.csv")),
        "drift_report": _records(_read_csv(base / "data_drift_report.csv")),
    }


@app.get("/decision/integrations")
def decision_integrations():
    base = DATA_PROCESSED_DIR / "decision_layer"
    health_path = base / "data_integrations_health.json"
    health = json.loads(health_path.read_text(encoding="utf-8")) if health_path.exists() else {}
    return {
        "health": health,
        "catalog": _records(_read_csv(base / "data_integrations_catalog.csv")),
    }


@app.get("/kpis")
def kpis(horizon: int = DEFAULT_FORECAST_HORIZON):
    recommendations = _read_csv(DATA_PROCESSED_DIR / "recommendations.csv")
    forecast = _read_csv(DATA_PROCESSED_DIR / f"forecast_{horizon}d.csv")
    metrics_path = DATA_PROCESSED_DIR / "model_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    decision_manifest_path = DATA_PROCESSED_DIR / "decision_layer" / "decision_layer_manifest.json"
    decision_manifest = json.loads(decision_manifest_path.read_text(encoding="utf-8")) if decision_manifest_path.exists() else {}
    return {
        "total_skus": int(forecast["sku"].nunique()),
        "total_locations": int(forecast["location_id"].nunique()),
        "forecast_rows": int(forecast.shape[0]),
        "forecast_total_units": round(float(forecast["predicted_quantity"].sum()), 2),
        "forecast_total_revenue_eur": round(float(forecast["predicted_revenue_eur"].sum()), 2),
        "stockout_risk_count": int((recommendations["recommended_action"] == "order").sum()),
        "overstock_count": int((recommendations["recommended_action"] == "reduce").sum()),
        "high_priority_count": int((recommendations["priority"] == "high").sum()),
        "forecast_accuracy": metrics.get("forecast_model_metrics", {}),
        "decision_layer": decision_manifest.get("row_counts", {}),
    }


@app.post("/decision/build")
def build_decision_layer(horizon: int = 21):
    return generate_decision_layer(DATA_RAW_DIR, DATA_PROCESSED_DIR, horizon=horizon)


@app.post("/refresh-outputs")
def refresh_outputs(payload: RefreshRequest):
    forecast_df = run_forecast(DATA_RAW_DIR, MODEL_DIR, DATA_PROCESSED_DIR, horizon=payload.horizon)
    generated = generate_recommendations(DATA_RAW_DIR, DATA_PROCESSED_DIR, horizon=payload.horizon)
    decision = generate_decision_layer(DATA_RAW_DIR, DATA_PROCESSED_DIR, horizon=min(payload.horizon, 21))
    return {
        "forecast_rows": int(forecast_df.shape[0]),
        "recommendations_rows": int(generated["recommendations"].shape[0]),
        "alerts_rows": int(generated["alerts"].shape[0]),
        "decision_layer": decision.get("row_counts", {}),
    }


@app.post("/retrain")
def retrain(payload: RetrainRequest):
    if payload.regenerate_dataset:
        generate_dataset(DATA_RAW_DIR, seed=payload.seed or 42)
    forecast_metrics = train_forecast_model(DATA_RAW_DIR, MODEL_DIR, DATA_PROCESSED_DIR, random_state=payload.seed or 42)
    cluster_metadata = train_cluster_model(DATA_RAW_DIR, MODEL_DIR, DATA_PROCESSED_DIR, random_state=payload.seed or 42)
    forecast_df = run_forecast(DATA_RAW_DIR, MODEL_DIR, DATA_PROCESSED_DIR, horizon=payload.horizon)
    rec = generate_recommendations(DATA_RAW_DIR, DATA_PROCESSED_DIR, horizon=payload.horizon)
    decision = generate_decision_layer(DATA_RAW_DIR, DATA_PROCESSED_DIR, horizon=min(payload.horizon, 21))
    return {
        "forecast_metrics": forecast_metrics.get("forecast_model_metrics", {}),
        "cluster_segments": cluster_metadata.get("segment_counts", {}),
        "forecast_rows": int(forecast_df.shape[0]),
        "recommendations_rows": int(rec["recommendations"].shape[0]),
        "decision_layer": decision.get("row_counts", {}),
    }
