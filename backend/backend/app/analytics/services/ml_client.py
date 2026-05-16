from __future__ import annotations

import csv
from datetime import date, timedelta
import json
import math
import os
from pathlib import Path
from typing import Any

import httpx


DEFAULT_ML_SERVICE_BASE_URL = os.getenv("ML_SERVICE_BASE_URL", "http://localhost:8001").rstrip("/")
DEFAULT_ML_TIMEOUT_SECONDS = float(os.getenv("ML_SERVICE_TIMEOUT_SECONDS", "5"))
REPO_ROOT = Path(__file__).resolve().parents[5]
BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ML_PROCESSED_DATA_DIR = REPO_ROOT / "ml" / "data" / "processed"
DEFAULT_ML_RAW_DATA_DIR = REPO_ROOT / "ml" / "data" / "raw"

MOCK_PARTS = {
    "PEU-WF-WINTER-5L": ("Lichid parbriz iarna -20C 5L", "Winter Fluids", 42.0),
    "PEU-WIPER-650": ("Stergatoare fata 650mm", "Wipers", 18.0),
    "PEU-BATT-70AH": ("Baterie 70Ah AGM/EFB", "Battery", 26.0),
    "PEU-AC-REFILL": ("Kit incarcare clima R134a/R1234yf", "AC Cooling", 30.0),
    "PEU-CABIN-CARBON": ("Filtru habitaclu cu carbon", "Filters", 24.0),
    "PEU-SUMMER-TIRE-205": ("Anvelopa vara 205/55R16", "Tires", 28.0),
    "PEU-WINTER-TIRE-205": ("Anvelopa iarna 205/55R16", "Tires", 34.0),
    "PEU-ANTIFREEZE-G12": ("Antigel G12 concentrat 1L", "Coolant", 22.0),
    "PEU-COOLANT-PREMIX": ("Lichid racire premix 5L", "Coolant", 20.0),
    "PEU-OIL-5W30-5L": ("Ulei motor 5W30 5L", "Maintenance", 23.0),
    "PEU-OIL-FILTER": ("Filtru ulei", "Maintenance", 20.0),
    "PEU-AIR-FILTER": ("Filtru aer motor", "Filters", 21.0),
    "PEU-BRAKE-PADS-F": ("Placute frana fata", "Brakes", 24.0),
    "PEU-HEADLIGHT-H7": ("Bec far H7", "Lighting", 16.0),
    "PEU-RUBBER-MATS": ("Covorase cauciuc Peugeot", "Accessories", 14.0),
    "PEU-ADBLUE-10L": ("AdBlue 10L", "Consumables", 18.0),
    "PEU-BRAKE-FLUID-DOT4": ("Lichid frana DOT4 1L", "Brakes", 16.0),
    "PEU-SPARK-PLUG": ("Bujie benzina", "Maintenance", 17.0),
}

MOCK_LOCATION_MULTIPLIER = {
    "FI_HEL": 1.16,
    "SE_STO": 1.13,
    "EE_TLL": 1.08,
    "DK_CPH": 1.05,
    "NL_AMS": 1.02,
    "DE_BER": 1.04,
    "PL_WAW": 1.0,
    "CZ_PRG": 0.98,
    "RO_BUC": 1.06,
    "IT_MIL": 0.96,
    "ES_MAD": 1.03,
    "FR_PAR": 1.01,
}


def default_location_id(current_user: dict) -> str | None:
    location_id = current_user.get("location_id")
    if location_id:
        return str(location_id)

    scoped_location_ids = current_user.get("user_location_ids") or []
    if scoped_location_ids:
        return str(scoped_location_ids[0])

    return None


def resolved_location_id(current_user: dict, requested_location: str | None = None) -> str | None:
    if requested_location and requested_location.strip():
        return requested_location.strip()
    return default_location_id(current_user)


def ml_service_get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{DEFAULT_ML_SERVICE_BASE_URL}{path}"
    with httpx.Client(timeout=DEFAULT_ML_TIMEOUT_SECONDS) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def safe_ml_service_get(path: str, params: dict[str, Any] | None = None) -> tuple[Any, str | None]:
    try:
        return ml_service_get(path, params=params), None
    except (httpx.HTTPError, ValueError) as error:
        return [], str(error)


def ml_service_post(
    path: str,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    url = f"{DEFAULT_ML_SERVICE_BASE_URL}{path}"
    with httpx.Client(timeout=DEFAULT_ML_TIMEOUT_SECONDS) as client:
        response = client.post(url, params=params, json=payload)
        response.raise_for_status()
        return response.json()


def safe_ml_service_post(
    path: str,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> tuple[Any, str | None]:
    try:
        return ml_service_post(path, payload=payload, params=params), None
    except (httpx.HTTPError, ValueError) as error:
        return {}, str(error)


def forecast_source_horizon(horizon: int) -> int:
    return 30 if horizon <= 30 else horizon


def ml_processed_data_dir() -> Path:
    configured_path = os.getenv("ML_PROCESSED_DATA_DIR")
    if not configured_path:
        return DEFAULT_ML_PROCESSED_DATA_DIR

    path = Path(configured_path)
    if path.is_absolute():
        return path
    return (BACKEND_ROOT / path).resolve()


def ml_raw_data_dir() -> Path:
    configured_path = os.getenv("ML_RAW_DATA_DIR")
    if not configured_path:
        return DEFAULT_ML_RAW_DATA_DIR

    path = Path(configured_path)
    if path.is_absolute():
        return path
    return (BACKEND_ROOT / path).resolve()


def _numeric(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def normalize_forecast_rows(
    rows: Any,
    *,
    requested_sku: str | None,
    requested_location: str | None,
    requested_horizon: int,
    limit: int,
) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []

    sku_filter = requested_sku.strip().upper() if requested_sku else None
    location_filter = requested_location.strip().upper() if requested_location else None
    normalized_rows: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        row_sku = str(row.get("sku") or "").upper()
        row_location = str(row.get("location_id") or row.get("location") or "").upper()
        horizon_day = _int_value(row.get("horizon_day"), len(normalized_rows) + 1)

        if sku_filter and row_sku != sku_filter:
            continue
        if location_filter and row_location != location_filter:
            continue
        if horizon_day < 1 or horizon_day > requested_horizon:
            continue

        next_row = dict(row)
        next_row["horizon_day"] = horizon_day
        next_row["predicted_quantity"] = round(_numeric(row.get("predicted_quantity")), 4)
        next_row["predicted_revenue_eur"] = round(_numeric(row.get("predicted_revenue_eur")), 2)
        normalized_rows.append(next_row)

    normalized_rows.sort(
        key=lambda item: (
            str(item.get("sku") or ""),
            str(item.get("location_id") or ""),
            _int_value(item.get("horizon_day")),
        )
    )
    return normalized_rows[:limit]


def read_forecast_csv(
    *,
    sku: str | None,
    location_id: str | None,
    requested_horizon: int,
    source_horizon: int,
    limit: int,
) -> tuple[list[dict[str, Any]], str | None]:
    path = ml_processed_data_dir() / f"forecast_{source_horizon}d.csv"
    if not path.exists():
        return [], f"Forecast CSV not found at {path}"

    try:
        with path.open("r", encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
    except OSError as error:
        return [], str(error)

    items = normalize_forecast_rows(
        rows,
        requested_sku=sku,
        requested_location=location_id,
        requested_horizon=requested_horizon,
        limit=limit,
    )
    if not items:
        return [], "Forecast CSV contained no rows for the requested filters"
    return items, None


def _read_csv_rows(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    if not path.exists():
        return [], f"CSV not found at {path}"

    try:
        with path.open("r", encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file)), None
    except OSError as error:
        return [], str(error)


def read_sales_history_csv(
    *,
    sku: str | None,
    location_id: str | None,
    start_date: str | None,
    end_date: str | None,
    limit: int,
) -> tuple[list[dict[str, Any]], str | None]:
    rows, error = _read_csv_rows(ml_raw_data_dir() / "sales_history.csv")
    if error:
        return [], error

    sku_filter = sku.strip().upper() if sku else None
    location_filter = location_id.strip().upper() if location_id else None
    filtered: list[dict[str, Any]] = []

    for row in rows:
        row_sku = str(row.get("sku") or "").upper()
        row_location = str(row.get("location_id") or "").upper()
        row_date = str(row.get("date") or "")
        if sku_filter and row_sku != sku_filter:
            continue
        if location_filter and row_location != location_filter:
            continue
        if start_date and row_date < start_date:
            continue
        if end_date and row_date > end_date:
            continue
        filtered.append(row)

    filtered.sort(key=lambda item: str(item.get("date") or ""))
    if not start_date and not end_date:
        filtered = filtered[-limit:]
    else:
        filtered = filtered[:limit]

    if not filtered:
        return [], "Sales history CSV contained no rows for the requested filters"
    return filtered, None


def read_open_meteo_csv(
    *,
    location_id: str | None,
    start_date: str | None,
    end_date: str | None,
    limit: int,
) -> tuple[list[dict[str, Any]], str | None]:
    rows, error = _read_csv_rows(ml_raw_data_dir() / "weather_forecast_open_meteo.csv")
    if error:
        return [], error

    location_filter = location_id.strip().upper() if location_id else None
    filtered: list[dict[str, Any]] = []

    for row in rows:
        row_location = str(row.get("location_id") or "").upper()
        row_date = str(row.get("date") or "")
        if location_filter and row_location != location_filter:
            continue
        if start_date and row_date < start_date:
            continue
        if end_date and row_date > end_date:
            continue
        filtered.append(row)

    filtered.sort(key=lambda item: str(item.get("date") or ""))
    filtered = filtered[:limit]

    if not filtered:
        return [], "Open-Meteo CSV contained no rows for the requested filters"
    return filtered, None


def read_open_meteo_metadata() -> tuple[dict[str, Any], str | None]:
    path = ml_raw_data_dir() / "weather_forecast_open_meteo_metadata.json"
    if not path.exists():
        return {}, f"Metadata not found at {path}"

    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, ValueError) as error:
        return {}, str(error)


def build_mock_forecast_rows(
    *,
    sku: str | None,
    location_id: str | None,
    horizon: int,
    limit: int,
) -> list[dict[str, Any]]:
    normalized_sku = (sku or "PEU-WF-WINTER-5L").strip().upper()
    normalized_location = (location_id or "FI_HEL").strip().upper()
    part_name, category, base_demand = MOCK_PARTS.get(
        normalized_sku,
        (normalized_sku, "Forecast", 20.0),
    )
    location_multiplier = MOCK_LOCATION_MULTIPLIER.get(normalized_location, 1.0)
    seed = sum((index + 3) * ord(char) for index, char in enumerate(f"{normalized_sku}-{normalized_location}"))
    start_date = date.today()
    rows: list[dict[str, Any]] = []

    for day in range(1, min(horizon, limit) + 1):
        seasonal = math.sin((seed + day * 11) * 0.27) * 2.8
        trend = day * (0.42 if category not in {"Tires", "Winter Fluids"} else 0.85)
        predicted = max(1.0, base_demand * location_multiplier + seasonal + trend)
        forecast_date = start_date + timedelta(days=day - 1)
        rows.append(
            {
                "forecast_date": forecast_date.isoformat(),
                "horizon_day": day,
                "sku": normalized_sku,
                "part_name": part_name,
                "category": category,
                "location_id": normalized_location,
                "city": normalized_location,
                "predicted_quantity": round(predicted, 4),
                "predicted_revenue_eur": 0.0,
                "prediction_scope": "backend_mock_fallback",
                "weather_source": "mock",
            }
        )

    return rows
